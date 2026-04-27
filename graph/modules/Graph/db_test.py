import pymysql

conn = pymysql.connect(
    host='183.69.138.62',
    port=33666,
    user='hagongda',
    password='ha.G/o[tEst]n%gD*a',
    database='r_d_test',
    charset='utf8mb4'
)

try:
    with conn.cursor() as cursor:
        # 查看所有表
        cursor.execute("SHOW TABLES")
        tables = cursor.fetchall()
        print("数据库中的表：")
        for table in tables:
            print(f"  - {table[0]}")
        
        print("\n" + "="*50 + "\n")
        
        # 查询 T_STAFF 表的 TENANT_ID 和 DEPT_ID 字段
        sql = "SELECT TENANT_ID, DEPT_ID FROM `T_STAFF`"
        cursor.execute(sql)
        results = cursor.fetchall()
        
        print(f"T_STAFF 表数据 ({len(results)} 条)：")
        print(f"{'序号':<6}{'TENANT_ID':<20}{'DEPT_ID':<20}")
        print("-" * 50)
        
        for i, row in enumerate(results, 1):
            tenant_id = row[0] if row[0] is not None else "NULL"
            dept_id = row[1] if row[1] is not None else "NULL"
            print(f"{i:<6}{str(tenant_id):<20}{str(dept_id):<20}")
        
        # 也可以查看字段的唯一值分布
        print("\n" + "="*50)
        print("\n字段值统计：")
        
        # TENANT_ID 唯一值统计
        cursor.execute("SELECT TENANT_ID, COUNT(*) FROM `T_STAFF` GROUP BY TENANT_ID")
        tenant_stats = cursor.fetchall()
        print("TENANT_ID 值分布：")
        for tenant_id, count in tenant_stats:
            print(f"  {tenant_id if tenant_id is not None else 'NULL'}: {count} 条")
        
        # DEPT_ID 唯一值统计
        cursor.execute("SELECT DEPT_ID, COUNT(*) FROM `T_STAFF` GROUP BY DEPT_ID")
        dept_stats = cursor.fetchall()
        print("\nDEPT_ID 值分布：")
        for dept_id, count in dept_stats:
            print(f"  {dept_id if dept_id is not None else 'NULL'}: {count} 条")

    print("\n连接成功")
    
except Exception as e:
    print(f"查询出错: {e}")
    
finally:
    conn.close()