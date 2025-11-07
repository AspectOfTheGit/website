from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/')
def home():
    return "test worked i thnk"

@app.route('/api/test', methods=['POST'])
def test():
    data = request.json
    return jsonify({"received": data}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
