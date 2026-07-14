import asyncio
import logging
import threading
from dataclasses import dataclass, field
from typing import Callable, Dict, Optional, Set

from aiortc import RTCPeerConnection, RTCSessionDescription
from aiortc.contrib.media import MediaRelay

LOGGER = logging.getLogger("voice_relay")

SignalCallback = Callable[[str, str, dict], None]

media_relay = MediaRelay()


@dataclass
class RemoteTrackBinding:
    speaker_uuid: str
    sender: object
    track: object


@dataclass
class PeerState:
    sid: str
    uuid: str
    room: str
    peer_connection: RTCPeerConnection
    local_audio_track: Optional[object] = None
    remote_tracks: Dict[str, RemoteTrackBinding] = field(default_factory=dict)
    negotiation_lock: Optional[asyncio.Lock] = None
    closed: bool = False


@dataclass
class RoomState:
    room_id: str
    peers: Dict[str, PeerState] = field(default_factory=dict)
    active_speakers: Dict[str, object] = field(default_factory=dict)


class VoiceRelayService:
    def __init__(self, signal_callback: SignalCallback):
        self._signal_callback = signal_callback
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run_loop, name="voice-relay-loop", daemon=True)
        self._thread.start()
        self._rooms: Dict[str, RoomState] = {}
        self._peers_by_sid: Dict[str, PeerState] = {}

    def _run_loop(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def _submit(self, coroutine):
        return asyncio.run_coroutine_threadsafe(coroutine, self._loop)

    def join(self, sid: str, room_id: str, uuid: str):
        return self._submit(self._join(sid, room_id, uuid))

    def answer(self, sid: str, sdp: str, sdp_type: str = "answer"):
        return self._submit(self._answer(sid, sdp, sdp_type))

    def renegotiate(self, sid: str):
        return self._submit(self._renegotiate(sid))

    def leave(self, sid: str):
        return self._submit(self._leave(sid))

    def shutdown(self):
        future = self._submit(self._shutdown())
        future.result(timeout=10)
        self._loop.call_soon_threadsafe(self._loop.stop)

    async def _wait_for_ice_gathering(self, peer_connection: RTCPeerConnection) -> None:
        while peer_connection.iceGatheringState != "complete":
            await asyncio.sleep(0.05)

    def _get_or_create_room(self, room_id: str) -> RoomState:
        room = self._rooms.get(room_id)
        if room is None:
            room = RoomState(room_id=room_id)
            self._rooms[room_id] = room
        return room

    def _signal(self, sid: str, event: str, payload: dict) -> None:
        try:
            self._signal_callback(sid, event, payload)
        except Exception:
            LOGGER.exception("voice relay signaling failed for %s", sid)

    async def _send_offer(self, peer: PeerState) -> None:
        if peer.negotiation_lock is None:
            peer.negotiation_lock = asyncio.Lock()

        async with peer.negotiation_lock:
            if peer.closed:
                return

            try:
                offer = await peer.peer_connection.createOffer()
                await peer.peer_connection.setLocalDescription(offer)
                await self._wait_for_ice_gathering(peer.peer_connection)

                track_map = []
                for transceiver in peer.peer_connection.getTransceivers():
                    sender = getattr(transceiver, "sender", None)
                    if sender is None:
                        continue

                    for binding in peer.remote_tracks.values():
                        if binding.sender == sender:
                            track_map.append({
                                "mid": transceiver.mid,
                                "peer": binding.speaker_uuid,
                            })
                            break

                self._signal(
                    peer.sid,
                    "voice-relay-offer",
                    {
                        "sdp": peer.peer_connection.localDescription.sdp,
                        "sdpType": peer.peer_connection.localDescription.type,
                        "tracks": track_map,
                    },
                )
            except Exception:
                LOGGER.exception("failed sending offer to %s", peer.uuid)
                self._signal(peer.sid, "voice-relay-error", {"message": "offer-failed"})

    async def _attach_track_to_peer(self, listener: PeerState, speaker_uuid: str, source_track: object) -> None:
        if listener.closed or speaker_uuid == listener.uuid:
            return

        if listener.remote_tracks.get(speaker_uuid) is not None:
            return

        cloned_track = media_relay.subscribe(source_track)
        sender = listener.peer_connection.addTrack(cloned_track)
        listener.remote_tracks[speaker_uuid] = RemoteTrackBinding(
            speaker_uuid=speaker_uuid,
            sender=sender,
            track=cloned_track,
        )

    async def _detach_track_from_peer(self, listener: PeerState, speaker_uuid: str) -> None:
        binding = listener.remote_tracks.pop(speaker_uuid, None)
        if binding is None:
            return

        try:
            listener.peer_connection.removeTrack(binding.sender)
        except Exception:
            LOGGER.debug("removeTrack unsupported or failed for %s -> %s", speaker_uuid, listener.uuid)

    async def _rebalance_room(self, room: RoomState) -> None:
        for listener in list(room.peers.values()):
            if listener.closed:
                continue

            desired_speakers: Set[str] = {
                speaker_uuid for speaker_uuid in room.active_speakers.keys()
                if speaker_uuid != listener.uuid
            }
            existing_speakers = set(listener.remote_tracks.keys())

            for speaker_uuid in sorted(desired_speakers - existing_speakers):
                await self._attach_track_to_peer(listener, speaker_uuid, room.active_speakers[speaker_uuid])

            for speaker_uuid in sorted(existing_speakers - desired_speakers):
                await self._detach_track_from_peer(listener, speaker_uuid)

            await self._send_offer(listener)

    async def _remove_peer(self, peer: PeerState) -> None:
        if peer.closed:
            return

        peer.closed = True
        room = self._rooms.get(peer.room)
        if room:
            room.peers.pop(peer.uuid, None)
            room.active_speakers.pop(peer.uuid, None)

            for listener in room.peers.values():
                listener.remote_tracks.pop(peer.uuid, None)

        self._peers_by_sid.pop(peer.sid, None)

        try:
            await peer.peer_connection.close()
        except Exception:
            LOGGER.exception("failed closing peer connection for %s", peer.uuid)

        if room:
            if room.peers:
                await self._rebalance_room(room)
            else:
                self._rooms.pop(room.room_id, None)

    async def _join(self, sid: str, room_id: str, uuid: str) -> None:
        existing = self._peers_by_sid.get(sid)
        if existing is not None:
            await self._remove_peer(existing)

        room = self._get_or_create_room(room_id)
        existing_room_peer = room.peers.get(uuid)
        if existing_room_peer is not None:
            await self._remove_peer(existing_room_peer)

        peer_connection = RTCPeerConnection()
        peer_connection.addTransceiver("audio", direction="recvonly")

        peer = PeerState(
            sid=sid,
            uuid=uuid,
            room=room_id,
            peer_connection=peer_connection,
            negotiation_lock=asyncio.Lock(),
        )
        self._peers_by_sid[sid] = peer

        @peer_connection.on("track")
        async def on_track(track):
            if track.kind != "audio":
                return

            LOGGER.info("audio track received for %s in %s", peer.uuid, peer.room)
            room = self._get_or_create_room(peer.room)
            peer.local_audio_track = track
            room.active_speakers[peer.uuid] = track
            await self._rebalance_room(room)

            @track.on("ended")
            async def on_ended():
                LOGGER.info("audio track ended for %s in %s", peer.uuid, peer.room)
                room.active_speakers.pop(peer.uuid, None)
                peer.local_audio_track = None
                await self._rebalance_room(room)

        room.peers[uuid] = peer
        await self._rebalance_room(room)

    async def _answer(self, sid: str, sdp: str, sdp_type: str = "answer") -> None:
        peer = self._peers_by_sid.get(sid)
        if peer is None or peer.closed:
            return

        try:
            await peer.peer_connection.setRemoteDescription(
                RTCSessionDescription(sdp=sdp, type=sdp_type)
            )
        except Exception:
            LOGGER.exception("failed applying answer for %s", peer.uuid)
            self._signal(peer.sid, "voice-relay-error", {"message": "answer-failed"})

    async def _renegotiate(self, sid: str) -> None:
        peer = self._peers_by_sid.get(sid)
        if peer is None or peer.closed:
            return

        await self._send_offer(peer)

    async def _leave(self, sid: str) -> None:
        peer = self._peers_by_sid.get(sid)
        if peer is None:
            return

        await self._remove_peer(peer)

    async def _shutdown(self) -> None:
        peers = list(self._peers_by_sid.values())
        for peer in peers:
            await self._remove_peer(peer)


_service: Optional[VoiceRelayService] = None


def init_voice_relay(signal_callback: SignalCallback) -> VoiceRelayService:
    global _service

    if _service is None:
        _service = VoiceRelayService(signal_callback)

    return _service


def get_voice_relay() -> VoiceRelayService:
    if _service is None:
        raise RuntimeError("voice relay service has not been initialized")

    return _service


def shutdown_voice_relay() -> None:
    global _service

    if _service is None:
        return

    _service.shutdown()
    _service = None
