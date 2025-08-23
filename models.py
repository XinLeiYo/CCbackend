from database import get_connection

def fetch_equipment(ccm_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT CCM_ID, CC_SIZE, USER_NAME, BOX_ID, 
               FORMAT(CC_STARTTIME, 'yyyy-MM-dd HH:mm') as CC_STARTTIME, 
               CC_STATUS, CC_SUBSTATUS, UPDATE_BY, 
               FORMAT(UPDATE_TIME, 'yyyy-MM-dd HH:mm') as UPDATE_TIME, 
               COMMENT 
        FROM CC_MASTER
        WHERE CCM_ID = ?
    """, ccm_id)
    row = cursor.fetchone()
    conn.close()
    if row:
        columns = [column[0] for column in cursor.description]
        return dict(zip(columns, row))
    return None

def fetch_logs(ccm_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT FORMAT(INPUT_DATE, 'yyyy-MM-dd HH:mm') AS INPUT_DATE,
               CC_STATUS, CC_SUBSTATUS, UPDATE_BY, 
               FORMAT(UPDATE_TIME, 'yyyy-MM-dd HH:mm') AS UPDATE_TIME,
               COMMENT
        FROM CC_LOG
        WHERE CC_ID_FK = ?
        ORDER BY INPUT_DATE DESC
    """, ccm_id)
    rows = cursor.fetchall()
    columns = [column[0] for column in cursor.description]
    conn.close()
    return [dict(zip(columns, row)) for row in rows]