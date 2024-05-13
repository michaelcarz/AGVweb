from flask import Flask, jsonify, render_template, request
import requests
import mysql.connector
from dbutils.pooled_db import PooledDB

app = Flask(__name__)
app.config.from_pyfile('config.cfg')  # 讀取配置文件

# 創建連接池
pool = PooledDB(
    creator=mysql.connector,
    host=app.config['DB_HOST'],
    port=app.config['DB_PORT'],
    user=app.config['DB_USER'],
    password=app.config['DB_PASSWORD'],
    database=app.config['DB_DATABASE'],
    autocommit=True,
    charset='utf8mb4'
)
def get_db_connection():
    # 從連接池中獲取連接
    return pool.connection()

@app.route('/')
def index():
    # 渲染 main.html 文件
    return render_template('main.html')

@app.route('/agv_status', methods=['GET'])
def agv_status():
    api_url = 'http://192.168.2.91:8080/agv/getAllVehicleRunningState'
    response = requests.get(api_url)
    if response.status_code == 200:
        agv_data = response.json()
        status_info = []
        for agv in agv_data['data']:
            # 從返回的數據中提取需要的信息
            agv_info = {
                'serialNo': agv['serialNo'], #當前任務
                'battery': agv['battery'], #電量
                'nodeId': agv['nodeId'],  # 使用 nodeId 作為當前位置
                'agvState': agv['agvState'] #當前狀態
            }
            status_info.append(agv_info)

            # 使用 log_info 函數記錄每個 AGV 的狀態到 info_log 資料表
            log_info(agv['serialNo'], agv['battery'], agv['nodeId'], agv['agvState'])

        return jsonify(status_info)
    else:
        return jsonify({'error': 'Unable to fetch AGV status'}), 500

def send_task_request(operation_id):
    api_url = f"http://192.168.2.91:8080/tabletOrder/distributeOrder/{operation_id}"
    response = requests.get(api_url)
    return response.json(), response.status_code  # 返回響應內容和狀態碼

@app.route('/charge', methods=['POST'])
def charge_agv():
    operation_id = app.config['CHARGE_AGV_ID']
    response_content, status_code = send_task_request(operation_id)
    log_action(operation_id, 'charge_agv', status_code)  # 添加記錄操作，包括狀態碼
    return jsonify(response_content), status_code

@app.route('/c1_recieve', methods=['POST'])
def c1_recieve():
    operation_id = app.config['C1_RECIEVE']
    response_content, status_code = send_task_request(operation_id)
    log_action(operation_id, 'c1_recieve', status_code)
    return jsonify(response_content), status_code

@app.route('/c2_recieve', methods=['POST'])
def c2_recieve():
    operation_id = app.config['C2_RECIEVE']
    response_content, status_code = send_task_request(operation_id)
    log_action(operation_id, 'c2_recieve', status_code)
    return jsonify(response_content), status_code

@app.route('/c1_replenish', methods=['POST'])
def c1_replenish():
    operation_id = app.config['C1_REPLENISH']
    response_content, status_code = send_task_request(operation_id)
    log_action(operation_id, 'c1_replenish', status_code)
    return jsonify(response_content), status_code

########this is new button
@app.route('/c2_replenish', methods=['POST'])
def c2_replenish():
    operation_id = app.config['C2_REPLENISH']
    response_content, status_code = send_task_request(operation_id)
    log_action(operation_id, 'c2_replenish', status_code)
    return jsonify(response_content), status_code
@app.route('/new_replenish', methods=['POST'])
def new_replenish():
    operation_id = app.config['NEW_REPLENISH']
    response_content, status_code = send_task_request(operation_id)
    log_action(operation_id, 'new_replenish', status_code)
    return jsonify(response_content), status_code
#########
@app.route('/pause', methods=['GET'])
def suspend_order():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT order_id FROM info_log ORDER BY timestamp DESC LIMIT 1")
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    if row is None:
        return jsonify({'error': 'No order_id found in info_log'}), 404
    order_id = row[0]
    suspend_url = f"http://192.168.2.91:8080/order/suspend/{order_id}"
    response = requests.get(suspend_url)
    log_action(order_id, 'suspend', response.status_code)
    return jsonify(response.json())

@app.route('/resume', methods=['GET'])
def resume_order():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT order_id FROM info_log ORDER BY timestamp DESC LIMIT 1")
    row = cursor.fetchone()
    cursor.close()
    conn.close()

    if row is None:
        return jsonify({'error': 'No order_id found in info_log'}), 404

    order_id = row[0]
    resume_url = f"http://192.168.2.91:8080/order/resume/{order_id}"
    response = requests.get(resume_url)
    log_action(order_id, 'resume', response.status_code)
    return jsonify(response.json())

def log_action(action_type, order_id=None, code=None): #儲存資料庫
    conn = get_db_connection()
    cursor = conn.cursor()
    query = "INSERT INTO action_log (order_id, action_type, timestamp, code) VALUES (%s, %s, NOW(), %s)"
    cursor.execute(query, (order_id, action_type, code))
    conn.commit()
    cursor.close()
    conn.close()

def log_info(serialNo, battery, nodeId, agvState):
    conn = get_db_connection()
    cursor = conn.cursor()

    # 檢查是否已有對應的記錄
    cursor.execute("SELECT * FROM info_log WHERE serialNo = %s", (serialNo,))
    record = cursor.fetchone()
    if record:
        # 如果記錄已存在，則更新
        query = """
        UPDATE info_log
        SET battery = %s, nodeId = %s, agvState = %s
        WHERE serialNo = %s
        """
        cursor.execute(query, (battery, nodeId, agvState, serialNo))
    else:
        # 如果記錄不存在，則插入
        query = """
        INSERT INTO info_log (serialNo, battery, nodeId, agvState)
        VALUES (%s, %s, %s, %s)
        """
        cursor.execute(query, (serialNo, battery, nodeId, agvState))

    conn.commit()
    cursor.close()
    conn.close()
    
if __name__ == '__main__':
    app.run(host='0.0.0.0', port= 5000, debug=True)
