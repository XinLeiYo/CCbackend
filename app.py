# app.py

from flask import Flask, request, jsonify, g, send_from_directory
from flask_cors import CORS
import os
import json
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from flask_jwt_extended import create_access_token, JWTManager, jwt_required, get_jwt_identity
from datetime import timedelta
import logging

# ===============================================
# 資料庫連線
# ===============================================
DATABASE_URL = os.environ.get('DATABASE_URL')
def get_db_connection():
        if "db" not in g:
                try:
                        # 建立連線
                        g.db = psycopg2.connect(DATABASE_URL)
                        logging.debug("成功建立 PostgreSQL 連線")
                except Exception as ex:
                        logging.error(f"資料庫連線失敗: {ex}")
                        return None
        return g.db

def init_db():
        """在伺服器啟動時，檢查並建立必要的資料表"""
        # 注意：這裡不能用 g.db，因為這不在 Request 內，要手動連線
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        
        try:
                # 1. 建立 CC_USER 表 (PostgreSQL 語法)
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS CC_USER (
                        ID SERIAL PRIMARY KEY,
                        USER_NAME VARCHAR(50) UNIQUE NOT NULL,
                        PASSWORD TEXT NOT NULL
                );
                """)

                # 2. 建立 CC_MASTER 表
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS CC_MASTER (
                        CCM_ID VARCHAR(50) PRIMARY KEY,
                        CC_SIZE VARCHAR(20),
                        BOX_ID VARCHAR(50),
                        USER_NAME VARCHAR(50),
                        CC_STARTTIME TIMESTAMP,
                        UPD_CNT INTEGER DEFAULT 0
                );
                """)

                # 3. 建立 CC_LOG 表
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS CC_LOG (
                        CCL_ID SERIAL PRIMARY KEY,
                        CC_ID_FK VARCHAR(50) REFERENCES CC_MASTER(CCM_ID) ON DELETE CASCADE,
                        INPUT_DATE TIMESTAMP,
                        CC_STATUS VARCHAR(50),
                        CC_SUBSTATUS VARCHAR(50),
                        UPDATE_BY VARCHAR(50),
                        UPDATE_TIME TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        COMMENT TEXT
                );
                """)
                
                # 4. 建立 CC_REPORT 表
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS CC_REPORT (
                        ID SERIAL PRIMARY KEY,
                        CCM_ID_FK VARCHAR(50),
                        REPORTER VARCHAR(50),
                        REPORT_TIME TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        ISSUE_TYPE VARCHAR(50),
                        ISSUE_INFO TEXT,
                        IMAGE_PATH TEXT,
                        STATUS VARCHAR(20) DEFAULT '待處理',
                        PROCESSER VARCHAR(50),
                        PROCESS_TIME TIMESTAMP,
                        PROCESS_NOTES TEXT
                );
                """)

                conn.commit()
                print("✅ 資料庫初始化完成（或已存在）")
        except Exception as e:
                print(f"❌ 資料庫初始化失敗: {e}")
                conn.rollback()
        finally:
                cursor.close()
                conn.close()

        # 調整 row_to_dict (PostgreSQL 有更方便的寫法，但為了相容你的舊代碼可以保留)
def row_to_dict(row):
        return dict(row)

# ===============================================
# Flask 和 JWT 配置
# ===============================================

# 設定日誌記錄
logging.basicConfig(level=logging.DEBUG)

frontend_url = os.environ.get('FRONTEND_URL', 'https://ccfrontend-dnk0.onrender.com')
app = Flask(__name__)
# 在 Flask App 啟動前執行
with app.app_context():
        init_db()
CORS(app, resources={
        r"/*": {
                "origins": ["*"],
                "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
                "allow_headers": ["Content-Type", "Authorization"]
        }
})

# 從環境變數設定 JWT 密鑰
app.config['JWT_SECRET_KEY'] = os.environ.get('JWT_SECRET_KEY', 'My@SecretKey')
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(minutes=60)
app.config['UPLOAD_FOLDER'] = 'static/uploads' 
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024 # 16 MB

jwt = JWTManager(app)


# ===============================================
# 應用程式配置
# ===============================================
# 圖片上傳目錄
if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])
        print(f"📁 已建立上傳資料夾: {app.config['UPLOAD_FOLDER']}")

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
def allowed_file(filename):
        return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.teardown_appcontext
def close_db_connection(exception=None):
        db = g.pop('db', None)
        if db is not None:
                db.close()
                print("✅ 資料庫連線已關閉")

def row_to_dict(row):
        return {column[0]: row[i] for i, column in enumerate(row.cursor_description)}

# ===============================================
# 輔助函數
# ===============================================
def allowed_file(filename):
        return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'png', 'jpg', 'jpeg', 'gif'}

# ===============================================
# 登入 API
# ===============================================
@app.route("/api/auth/login", methods=["POST"])
def login():
        conn = get_db_connection()
        if conn is None:
                return jsonify({"success": False, "error": "資料庫連線失敗"}), 500
        
        try:
                data = request.get_json()
                username = data.get("username")
                password = data.get("password")
                if not username or not password:
                        return jsonify({"success": False, "error": "請提供使用者名稱和密碼"}), 400

                cursor = conn.cursor()
                cursor.execute('SELECT "PASSWORD" FROM "CC_USER" WHERE "USER_NAME" = %s', (username,))
                user_row = cursor.fetchone()

                if user_row and check_password_hash(user_row.PASSWORD, password):
                        access_token = create_access_token(identity=username)
                        return jsonify({
                                "success": True,
                                "message": "登入成功",
                                "access_token": access_token,
                                "username": username
                        }), 200
                else:
                        return jsonify({"success": False, "error": "使用者名稱或密碼錯誤"}), 401
        except Exception as e:
                print(f"登入錯誤: {e}")
                return jsonify({"success": False, "error": "伺服器錯誤"}), 500

# 使用者名稱驗證
@app.route("/api/auth/verify_username", methods=["POST", "OPTIONS"])
def verify_username():
        conn = get_db_connection()
        if conn is None:
                return jsonify({"success": False, "error": "資料庫連線失敗"}), 500
        try:
                data = request.get_json()
                username = data.get("username")
                if not username:
                        return jsonify({"success": False, "error": "請提供使用者名稱"}), 400

                cursor = conn.cursor()
                cursor.execute(
                        "SELECT COUNT(*) FROM CC_USER WHERE USER_NAME = %s", (username,)
                )
                if cursor.fetchone()[0] > 0:
                        return jsonify({"success": True, "message": "使用者名稱存在"}), 200
                else:
                        return jsonify({"success": False, "error": "使用者不存在"}), 404
        except Exception as e:
                logging.error(f"驗證使用者名稱錯誤: {e}")
                return jsonify({"success": False, "error": "伺服器錯誤"}), 500

# 註冊 API
@app.route("/api/register", methods=["POST"])
def register():
        conn = get_db_connection()
        if conn is None:
                return jsonify({"success": False, "error": "資料庫連線失敗"}), 500

        try:
                data = request.get_json()
                username = data.get("username")
                password = data.get("password")

                if not username or not password:
                        return jsonify({"success": False, "error": "請提供使用者名稱和密碼"}), 400

                # 檢查帳號是否已存在
                cursor = conn.cursor()
                cursor.execute("SELECT USER_NAME FROM [CC_USER] WHERE USER_NAME = %s", (username,))
                existing_user = cursor.fetchone()
                if existing_user:
                        return jsonify({"success": False, "error": "使用者名稱已存在"}), 409

                # 雜湊密碼
                hashed_password = generate_password_hash(password)

                # 插入新使用者
                cursor.execute(
                        "INSERT INTO [CC_USER] (USER_NAME, PASSWORD) VALUES (%s, %s)",
                        (username, hashed_password)
                )
                conn.commit()

                return jsonify({"success": True, "message": "帳號註冊成功"}), 201

        except Exception as e:
                conn.rollback()
                print(f"註冊錯誤: {e}")
                return jsonify({"success": False, "error": "伺服器錯誤"}), 500
        finally:
                pass

@app.route("/api/auth/reset_password_no_auth", methods=["POST"])
def reset_password_no_auth():
        conn = get_db_connection()
        if conn is None:
                return jsonify({"success": False, "error": "資料庫連線失敗"}), 500

        try:
                data = request.get_json()
                username = data.get("username")
                new_password = data.get("new_password")

                if not username or not new_password:
                        return jsonify({"success": False, "error": "請提供使用者名稱和新密碼"}), 400

                cursor = conn.cursor()
                cursor.execute(
                        "SELECT COUNT(*) FROM CC_USER WHERE USER_NAME = %s", (username,)
                )
                if cursor.fetchone()[0] == 0:
                        return jsonify({"success": False, "error": "使用者不存在"}), 404

                hashed_password = generate_password_hash(new_password)
                cursor.execute(
                        "UPDATE [CC_USER] SET PASSWORD = %s WHERE USER_NAME = %s",
                (hashed_password, username)
                )
                conn.commit()

                return jsonify({
                        "success": True,
                        "message": f"使用者 {username} 的密碼已成功重設。",
                }), 200

        except Exception as e:
                conn.rollback()
                logging.error(f"直接重設密碼錯誤: {e}")
                return jsonify({"success": False, "error": "伺服器錯誤"}), 500


# 忘記密碼 API(信箱修改暫時沒用到)
@app.route("/api/auth/forgot_password", methods=["POST"])
def forgot_password():
        conn = get_db_connection()
        if conn is None:
                return jsonify({"success": False, "error": "資料庫連線失敗"}), 500

        try:
                data = request.get_json()
                username = data.get("username")

                if not username:
                        return jsonify({"success": False, "error": "請提供使用者名稱"}), 400

                cursor = conn.cursor()
                cursor.execute(
                        "SELECT COUNT(*) FROM CC_USER WHERE USER_NAME = %s", (username,)
                )
                user_exists = cursor.fetchone()[0]

                if user_exists == 0:
                        return jsonify({"success": False, "error": "使用者不存在"}), 404

                # 這裡由於沒有郵件服務，我們只回傳成功訊息
                # 實際應用中，這裡會發送一封包含重設連結的郵件
                return jsonify({
                        "success": True,
                        "message": f"已發送重設密碼指示到註冊的信箱。請檢查您的信箱。",
                }), 200

        except Exception as e:
                print(f"忘記密碼請求錯誤: {e}")
                return jsonify({"success": False, "error": "伺服器錯誤"}), 500

# 重設密碼 API(要登入)
@app.route("/api/reset_password", methods=["PUT"])
@jwt_required()
def reset_password():
        conn = get_db_connection()
        if conn is None:
                return jsonify({"success": False, "error": "資料庫連線失敗"}), 500

        try:
                current_user = get_jwt_identity()
                data = request.get_json()
                target_username = data.get("target_username")
                new_password = data.get("new_password")

                if not target_username or not new_password:
                        return jsonify({"success": False, "error": "請提供目標使用者和新密碼"}), 400

                hashed_password = generate_password_hash(new_password)

                cursor = conn.cursor()
                cursor.execute(
                        "UPDATE [CC_USER] SET PASSWORD = %s WHERE USER_NAME = %s",
                        (hashed_password, target_username)
                )
                conn.commit()

                if cursor.rowcount == 0:
                        return jsonify({"success": False, "error": "未找到該使用者"}), 404

                return jsonify({
                        "success": True,
                        "message": f"使用者 {target_username} 的密碼已成功重設。"
                }), 200

        except Exception as e:
                conn.rollback()
                print(f"重設密碼錯誤: {e}")
                return jsonify({"success": False, "error": "伺服器錯誤"}), 500
        finally:
                pass

# ===============================================
# 器材管理 API
# ===============================================
# 獲取所有器材
@app.route("/api/equipment", methods=["GET"])
@jwt_required()
def get_equipment_data():
        conn = get_db_connection()
        if conn is None:
                return jsonify({"success": False, "error": "資料庫連線失敗"}), 500
        try:
                cursor = conn.cursor()
                
                cursor.execute("""
                        UPDATE CC_MASTER
                        SET UPD_CNT = (
                                SELECT COUNT(*)
                                FROM CC_LOG
                                WHERE CC_ID_FK = CC_MASTER.CCM_ID
                        )
                """)
                conn.commit()  # 提交變更，確保資料庫內容已更新
                
                cursor.execute("""
                        SELECT 
                                M.CCM_ID,
                                M.CC_SIZE,
                                M.BOX_ID,
                                M.USER_NAME,
                                M.CC_STARTTIME,
                                M.UPD_CNT,
                                L.CC_STATUS,
                                L.CC_SUBSTATUS,
                                L.COMMENT,
                                L.UPDATE_BY,
                                L.UPDATE_TIME
                        FROM 
                                CC_MASTER M
                        LEFT JOIN 
                                CC_LOG L ON M.CCM_ID = L.CC_ID_FK
                        WHERE 
                                L.CCL_ID = (SELECT MAX(CCL_ID) FROM CC_LOG WHERE CC_ID_FK = M.CCM_ID)
                                OR L.CCL_ID IS NULL
                        ORDER BY
                                M.CCM_ID
                """)
                columns = [column[0] for column in cursor.description]
                equipment_list = [dict(zip(columns, row)) for row in cursor.fetchall()]

                # 處理日期時間格式
                for item in equipment_list:
                        if item.get('開始時間') and isinstance(item['開始時間'], datetime):
                                item['開始時間'] = item['開始時間'].strftime('%Y-%m-%d %H:%M:%S')
                        if item.get('狀態更新時間') and isinstance(item['狀態更新時間'], datetime):
                                item['狀態更新時間'] = item['狀態更新時間'].strftime('%Y-%m-%d %H:%M:%S')
                        if item.get('UPD_CNT') is None:
                                item['UPD_CNT'] = 0
                return jsonify(equipment_list), 200
        except Exception as e:
                print(f"❌ 獲取器材資料錯誤: {e}")
                return jsonify({"success": False, "error": "伺服器錯誤"}), 500
        finally:
                pass

# 新增器材
@app.route("/api/equipment", methods=["POST"])
@jwt_required()
def add_equipment():
        conn = get_db_connection()
        if conn is None:
                return jsonify({"success": False, "error": "資料庫連線失敗"}), 500

        try:
                current_user = get_jwt_identity()
                if not request.is_json:
                        print("❌ 請求 Content-Type 不是 'application/json'")
                        return jsonify({"success": False, "error": "請求格式錯誤，請使用 JSON"}), 400
                # 專門用來解析 JSON 的 try...except 區塊
                try:
                        data = request.json
                        if data is None:
                                # 即使 is_json 是 True，JSON 內容也可能是空的
                                print("❌ 請求的 JSON 資料為空。請確認客戶端發送了 JSON body。")
                                return jsonify({"success": False, "error": "請求的 JSON 資料為空"}), 400
                except Exception as e:
                        # 在解析 JSON 時發生錯誤，代表 JSON 格式無效
                        print(f"❌ 嘗試解析 JSON 資料時發生錯誤：{e}。請檢查客戶端 JSON 格式。")
                        return jsonify({"success": False, "error": "JSON 資料格式無效"}), 400

                # ❗❗ 只有當 JSON 成功解析後，才會執行這行偵錯輸出 ❗❗
                print(f"✅ 成功接收並解析 JSON 資料: {data}")
                ccm_id = data.get("CCM_ID")
                size = data.get("CC_SIZE")
                box_id = data.get("BOX_ID")
                user_name = data.get("USER_NAME")
                cc_start_time = data.get("CC_STARTTIME")
                status = data.get("CC_STATUS")
                substatus = data.get("CC_SUBSTATUS")
                comment = data.get("COMMENT")
                
                if not ccm_id:
                        print("❌ 請求中沒有找到 ccm_id。請確認 JSON 中有此欄位。")
                        return jsonify({"success": False, "error": "CCM ID 是必填項"}), 400

                cursor = conn.cursor()
                
                # 1. 插入一筆新的器材記錄到 CC_MASTER 表
                cursor.execute("""
                        INSERT INTO CC_MASTER (CCM_ID, CC_SIZE, BOX_ID, USER_NAME, CC_STARTTIME, UPD_CNT)
                        VALUES (%s, %s, %s, %s, %s, %s)
                """, (ccm_id, size, box_id, user_name, cc_start_time, 0))
                
                # 2. 插入一筆對應的日誌記錄到 CC_LOG 表
                cursor.execute(
                        """
                        INSERT INTO CC_LOG (CC_ID_FK, INPUT_DATE, CC_STATUS, CC_SUBSTATUS, UPDATE_BY, UPDATE_TIME, COMMENT)
                        VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP, %s)
                        """,
                        ccm_id, cc_start_time, status, substatus, current_user, comment
                )

                conn.commit()
                print(f"✅ 新增器材 {ccm_id} 成功。")
                return jsonify({"success": True, "message": f"器材 {ccm_id} 新增成功"}), 201
        
        except pyodbc.IntegrityError as e:
                # 如果 CCM ID 重複，會拋出 IntegrityError
                conn.rollback()
                print(f"❌ 新增器材錯誤 (IntegrityError): {e}")
                return jsonify({"success": False, "error": "CCM ID 已存在，請使用不同的 ID"}), 409
        
        except Exception as e:
                # 處理所有其他可能的錯誤
                conn.rollback()
                print(f"❌ 新增器材錯誤: {e}")
                return jsonify({"success": False, "error": "伺服器錯誤"}), 500

# 更新器材
@app.route("/api/equipment/<string:ccm_id>", methods=["PUT"])
@jwt_required()
def update_equipment(ccm_id):
        conn = get_db_connection()
        if conn is None:
                return jsonify({"success": False, "error": "資料庫連線失敗"}), 500
        data = request.json
        if not data:
                print("❌ 請求中沒有找到有效的 JSON 資料")
                return jsonify({"success": False, "error": "無效的 JSON 資料"}), 400
        try:
                current_user = get_jwt_identity()
                ccm_id = ccm_id.strip()
                
                print(f"收到的 CCM_ID: '{ccm_id}'")
                print(f"✅ 成功接收更新請求：CCM_ID='{ccm_id}'")
                print(f"ℹ️ 登入使用者：'{current_user}'")
                print(f"ℹ️ 接收到的資料：{data}")
                size = data.get("CC_SIZE")
                box_id = data.get("BOX_ID")
                user_name = data.get("USER_NAME")
                cc_start_time = data.get("CC_STARTTIME")
                status = data.get("CC_STATUS")
                substatus = data.get("CC_SUBSTATUS")
                comment = data.get("COMMENT")   

                if not cc_start_time or not status:
                        return jsonify({"success": False, "error": "缺少必要欄位 (CC_STARTTIME 或 CC_STATUS)"}), 400


                cursor = conn.cursor()
                
                cursor.execute("SELECT UPD_CNT FROM CC_MASTER WHERE CCM_ID = %s", ccm_id)
                result = cursor.fetchone()
                
                if result is None:
                        return jsonify({"success": False, "error": "未找到該器材"}), 404
                
                current_upd_cnt = result[0] if result[0] is not None else 0
                new_upd_cnt = current_upd_cnt + 1

                cursor.execute(
                        """
                        UPDATE CC_MASTER SET
                        CC_SIZE = %s, BOX_ID = %s, USER_NAME = %s, CC_STARTTIME = %s,
                        UPD_CNT = %s
                        WHERE CCM_ID = %s
                        """,
                        size, box_id, user_name, cc_start_time, new_upd_cnt, ccm_id
                )
                
                cursor.execute(
                        """
                        INSERT INTO CC_LOG (CC_ID_FK, INPUT_DATE, CC_STATUS, CC_SUBSTATUS, UPDATE_BY, UPDATE_TIME, COMMENT)
                        VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP, %s)
                        """,
                        ccm_id, cc_start_time, status, substatus, current_user, comment
                )

                conn.commit()
                
                return jsonify({"success": True, "message": "器材更新成功"}), 200
        except Exception as e:
                conn.rollback()
                print(f"❌ 更新器材錯誤: {e}")
                return jsonify({"success": False, "error": "伺服器錯誤"}), 500
        finally:
                pass

# 批次更新器材
@app.route("/api/equipment/batch", methods=["PUT"])
@jwt_required()
def batch_update_equipment():
        """
        接收一個 JSON 列表，對多個器材進行彈性批次更新，並記錄日誌。
        """
        conn = get_db_connection()
        if conn is None:
                return jsonify({"success": False, "error": "資料庫連線失敗"}), 500

        try:
                current_user = get_jwt_identity()
                updates = request.json
                
                if not isinstance(updates, list) or not updates:
                        return jsonify({"success": False, "error": "請求數據格式不正確，應為非空列表"}), 400

                cursor = conn.cursor()
                successful_updates = []

                for item in updates:
                        ccm_id = item.get("CCM_ID")
                        if not ccm_id:
                                print(f"❌ 批次更新中發現無效的器材項目: {item}")
                                continue # 跳過沒有 CCM_ID 的項目

                        # 提取更新資料 (這些資料只用於日誌記錄)
                        status = item.get("CC_STATUS")
                        substatus = item.get("CC_SUBSTATUS")
                        comment = item.get("COMMENT")

                        # 檢查是否有任何更新欄位
                        if not any([status, substatus, comment]):
                                print(f"❌ 器材 {ccm_id} 沒有提供任何更新欄位，跳過。")
                                continue
                        
                        cursor.execute(
                                "UPDATE CC_MASTER SET UPD_CNT = COALENCE(UPD_CNT, 0) + 1 WHERE CCM_ID = %s",
                                ccm_id.strip()
                        )
                        
                        log_substatus = substatus if substatus else status
                        
                        cursor.execute(
                                """
                                INSERT INTO CC_LOG (CC_ID_FK, INPUT_DATE, CC_STATUS, CC_SUBSTATUS, UPDATE_BY, UPDATE_TIME, COMMENT)
                                VALUES (%s, CURRENT_TIMESTAMP, %s, %s, %s, CURRENT_TIMESTAMP, %s)
                                """,
                                ccm_id.strip(), status, log_substatus, current_user, comment
                        )
                        
                        successful_updates.append(ccm_id)
                        
                conn.commit()
                        
                return jsonify({"success": True, "message": f"成功更新 {len(successful_updates)} 筆資料", "updated_ids": successful_updates}), 200
        except Exception as e:
                conn.rollback()
                print(f"❌ 批次更新錯誤: {e}")
                return jsonify({"success": False, "error": f"伺服器錯誤: {e}"}), 500

# 刪除器材
@app.route("/api/equipment/<string:ccm_id>", methods=["DELETE"])
@jwt_required()
def delete_equipment(ccm_id):
        conn = get_db_connection()
        if conn is None:
                return jsonify({"success": False, "error": "資料庫連線失敗"}), 500

        try:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM CC_MASTER WHERE CCM_ID = %s", ccm_id)
                conn.commit()
                if cursor.rowcount == 0:
                        return jsonify({"success": False, "error": "未找到該器材"}), 404
                return jsonify({"success": True, "message": "器材刪除成功"}), 200
        except Exception as e:
                conn.rollback()
                print(f"❌ 刪除器材錯誤: {e}")
                return jsonify({"success": False, "error": "伺服器錯誤"}), 500
        finally:
                pass

# 取得器材狀態統計
@app.route("/api/equipment/status_counts", methods=["GET"])
@jwt_required()
def get_status_counts():
        conn = get_db_connection()
        if conn is None:
                return jsonify({"success": False, "error": "資料庫連線失敗"}), 500
        try:
                cursor = conn.cursor()
                cursor.execute("""
                        SELECT T1.CC_STATUS, COUNT(T1.CC_STATUS) AS count
                                FROM CC_LOG AS T1
                                JOIN (
                                        SELECT CC_ID_FK, MAX(UPDATE_TIME) AS MaxDateTime
                                        FROM CC_LOG
                                        GROUP BY CC_ID_FK
                                ) AS T2 ON T1.CC_ID_FK = T2.CC_ID_FK AND T1.UPDATE_TIME = T2.MaxDateTime
                                GROUP BY T1.CC_STATUS
                        """)
                status_counts = {row.CC_STATUS: row.count for row in cursor.fetchall()}
                return jsonify(status_counts), 200
        except Exception as e:
                print(f"❌ 獲取狀態計數錯誤: {e}")
                return jsonify({"success": False, "error": "伺服器錯誤"}), 500
        finally:
                pass

# 獲取器材日誌歷史
@app.route("/api/equipment/logs/<string:ccm_id>", methods=["GET"])
@jwt_required()
def get_log_history(ccm_id):
        conn = get_db_connection()
        if conn is None:
                return jsonify({"success": False, "error": "資料庫連線失敗"}), 500
        try:
                cursor = conn.cursor()
                # 你的歷史紀錄表格是 CC_LOG
                cursor.execute("SELECT * FROM CC_LOG WHERE CC_ID_FK = %s ORDER BY UPDATE_TIME DESC", ccm_id)
                columns = [column[0] for column in cursor.description]
                history_list = [dict(zip(columns, row)) for row in cursor.fetchall()]
                response_data = {
                        "success": True,
                        "data": history_list
                }
                return jsonify(response_data), 200
        except Exception as e:
                print(f"❌ 獲取日誌歷史錯誤: {e}")
                return jsonify({"success": False, "error": "伺服器錯誤"}), 500
        finally:
                pass

# ===============================================
# 問題回報 API
# ===============================================
@app.route("/api/report/upload", methods=["POST"])
@jwt_required()
def upload_report():
        conn = get_db_connection()
        if conn is None:
                return jsonify({"success": False, "error": "資料庫連線失敗"}), 500

        try:
                current_user = get_jwt_identity()
                
                files = request.files.getlist("images")
                ccm_id = request.form.get("ccm_id")
                issue_type = request.form.get("issue_type")
                issue_description = request.form.get("issue_description")
                
                status = "待處理"
                
                image_db_paths = []
                if files:
                        for file in files:
                                if file and allowed_file(file.filename):
                                        filename = secure_filename(file.filename)
                                        timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
                                        unique_filename = f"{timestamp}_{filename}"
                                        file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
                                        file.save(file_path)
                                        image_db_paths.append(f"/static/uploads/{unique_filename}")

                images_json = json.dumps(image_db_paths) if image_db_paths else None
                
                if not ccm_id or not issue_type:
                        return jsonify({"success": False, "error": "CCM ID 和問題類型為必填項"}), 400

                cursor = conn.cursor()
                # 你的 CC_REPORT 欄位為 CCM_ID_FK, REPORTER, ISSUE_TYPE, ISSUE_INFO, IMAGE_PATH
                cursor.execute(
                        """
                        INSERT INTO CC_REPORT 
                        (CCM_ID_FK, REPORTER, REPORT_TIME, ISSUE_TYPE, ISSUE_INFO, IMAGE_PATH,STATUS)
                        VALUES (%s, %s, CURRENT_TIMESTAMP, %s, %s, %s, %s)
                        """,
                        ccm_id, current_user, issue_type, issue_description, images_json, status
                )
                conn.commit()
                return jsonify({"success": True, "message": "回報上傳成功"}), 201

        except Exception as e:
                conn.rollback()
                print(f"❌ 上傳回報錯誤: {e}")
                return jsonify({"success": False, "error": str(e)}), 500
        finally:
                pass

@app.route("/api/reports", methods=["GET"])
@jwt_required()
def get_all_reports():
        conn = get_db_connection()
        if conn is None:
                return jsonify({"success": False, "error": "資料庫連線失敗"}), 500

        try:
                cursor = conn.cursor()
                # 你的 CC_REPORT 欄位名稱是 ID, CCM_ID_FK, REPORTER, REPORT_TIME, ...
                cursor.execute(
                        "SELECT ID, CCM_ID_FK, REPORTER, REPORT_TIME, ISSUE_TYPE, ISSUE_INFO, IMAGE_PATH, STATUS, PROCESSER, PROCESS_TIME, PROCESS_NOTES FROM CC_REPORT ORDER BY REPORT_TIME DESC"
                )
                
                rows = cursor.fetchall()
                
                reports = []
                for row in rows:
                        report_data = {
                                "ID": row.ID,
                                "CCM_ID_FK": row.CCM_ID_FK,
                                "REPORTER": row.REPORTER,
                                "REPORT_TIME": row.REPORT_TIME.strftime("%Y-%m-%d %H:%M:%S") if row.REPORT_TIME else None,
                                "ISSUE_TYPE": row.ISSUE_TYPE,
                                "ISSUE_INFO": row.ISSUE_INFO,
                                "IMAGE_PATH": row.IMAGE_PATH,
                                "STATUS": row.STATUS,
                                "PROCESSER": row.PROCESSER,
                                "PROCESS_TIME": row.PROCESS_TIME.strftime("%Y-%m-%d %H:%M:%S") if row.PROCESS_TIME else None,
                                "PROCESS_NOTES": row.PROCESS_NOTES
                        }
                        reports.append(report_data)
                        
                return jsonify({"success": True, "reports": reports}), 200

        except Exception as e:
                print(f"❌ 獲取回報資料錯誤: {e}")
                return jsonify({"success": False, "error": str(e)}), 500
        finally:
                pass

@app.route("/api/report/<int:report_id>", methods=["PUT"])
@jwt_required()
def update_report(report_id):
        conn = get_db_connection()
        if conn is None:
                return jsonify({"success": False, "error": "資料庫連線失敗"}), 500

        try:
                current_user = get_jwt_identity()
                data = request.json
                status = data.get('status')
                process_notes = data.get('process_notes')
                
                if not status:
                        return jsonify({"success": False, "error": "處理狀態為必填項"}), 400

                cursor = conn.cursor()
                sql = """
                        UPDATE CC_REPORT SET
                        STATUS = %s, PROCESSER = %s, PROCESS_NOTES = %s, PROCESS_TIME = CURRENT_TIMESTAMP
                        WHERE ID = %s
                """
                cursor.execute(sql, status, current_user, process_notes, report_id)
                conn.commit()

                if cursor.rowcount == 0:
                        return jsonify({"success": False, "error": "未找到該回報或沒有資料更新"}), 404
                        
                return jsonify({"success": True, "message": "回報資料更新成功"}), 200

        except Exception as e:
                conn.rollback()
                print(f"❌ 更新回報資料錯誤: {e}")
                return jsonify({"success": False, "error": str(e)}), 500
        finally:
                pass

@app.route("/api/report/<int:report_id>", methods=["DELETE"])
@jwt_required()
def delete_report(report_id):
        conn = get_db_connection()
        if conn is None:
                return jsonify({"success": False, "error": "資料庫連線失敗"}), 500

        try:
                cursor = conn.cursor()
                
                # 刪除圖片文件
                cursor.execute("SELECT IMAGE_PATH FROM CC_REPORT WHERE ID = %s", (report_id,))
                image_path_row = cursor.fetchone()
                if image_path_row and image_path_row.IMAGE_PATH:
                        file_to_delete = os.path.join(app.config['UPLOAD_FOLDER'], os.path.basename(image_path_row.IMAGE_PATH))
                        if os.path.exists(file_to_delete):
                                os.remove(file_to_delete)
                                print(f"✅ 已刪除圖片文件: {file_to_delete}")

                cursor.execute("DELETE FROM CC_REPORT WHERE ID = %s", (report_id,))
                conn.commit()

                if cursor.rowcount == 0:
                        return jsonify({"success": False, "error": "未找到該回報或沒有資料刪除"}), 404
                        
                return jsonify({"success": True, "message": "回報已成功刪除"}), 200

        except Exception as e:
                conn.rollback()
                print(f"❌ 刪除回報錯誤: {e}")
                return jsonify({"success": False, "error": str(e)}), 500
        finally:
                pass

@app.route('/uploads/<filename>')
def uploaded_file(filename):
        try:
        # 使用 send_from_directory 來安全地提供靜態檔案
                return send_from_directory(app.config['UPLOAD_FOLDER'], filename)
        except FileNotFoundError:
        # 如果檔案不存在，返回 404 錯誤
                return jsonify({"success": False, "error": "圖片檔案不存在"}), 404

# ===============================================
# 伺服器運行
# ===============================================
if __name__ == '__main__':
        app.run(host='0.0.0.0', port=5432, debug=True)