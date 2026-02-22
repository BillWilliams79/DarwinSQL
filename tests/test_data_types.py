"""
Test data type definitions and schema correctness.

Verifies that DESCRIBE output for each table matches the expected schema.sql
definitions. Uses darwin_dev test database (profiles, domains, areas, tasks).
"""


def test_profiles_columns(db_connection):
    """Verify profiles column definitions match schema.sql.

    Expected columns:
    - id: VARCHAR(64), PRI, NOT NULL
    - name: VARCHAR(256), NOT NULL
    - email: VARCHAR(256), NOT NULL
    - subject: VARCHAR(64), NOT NULL
    - userName: VARCHAR(256), NOT NULL
    - region: VARCHAR(128), NOT NULL
    - userPoolId: VARCHAR(128), NOT NULL
    - create_ts: TIMESTAMP, NULL, DEFAULT CURRENT_TIMESTAMP
    - update_ts: TIMESTAMP, NULL, ON UPDATE CURRENT_TIMESTAMP
    """
    with db_connection.cursor() as cur:
        cur.execute("DESCRIBE profiles")
        columns = {row['Field']: row for row in cur.fetchall()}

    # Verify all expected columns exist
    expected_fields = [
        'id', 'name', 'email', 'subject', 'userName', 'region', 'userPoolId',
        'create_ts', 'update_ts'
    ]
    assert set(columns.keys()) == set(expected_fields), \
        f"Unexpected columns: {set(columns.keys()) - set(expected_fields)}"

    # id: VARCHAR(64), PRI
    assert columns['id']['Type'] == 'varchar(64)'
    assert columns['id']['Key'] == 'PRI'
    assert columns['id']['Null'] == 'NO'

    # name: VARCHAR(256), NOT NULL
    assert columns['name']['Type'] == 'varchar(256)'
    assert columns['name']['Null'] == 'NO'

    # email: VARCHAR(256), NOT NULL
    assert columns['email']['Type'] == 'varchar(256)'
    assert columns['email']['Null'] == 'NO'

    # subject: VARCHAR(64), NOT NULL
    assert columns['subject']['Type'] == 'varchar(64)'
    assert columns['subject']['Null'] == 'NO'

    # userName: VARCHAR(256), NOT NULL
    assert columns['userName']['Type'] == 'varchar(256)'
    assert columns['userName']['Null'] == 'NO'

    # region: VARCHAR(128), NOT NULL
    assert columns['region']['Type'] == 'varchar(128)'
    assert columns['region']['Null'] == 'NO'

    # userPoolId: VARCHAR(128), NOT NULL
    assert columns['userPoolId']['Type'] == 'varchar(128)'
    assert columns['userPoolId']['Null'] == 'NO'

    # create_ts: TIMESTAMP, NULL, DEFAULT CURRENT_TIMESTAMP
    assert 'timestamp' in columns['create_ts']['Type']
    assert columns['create_ts']['Null'] == 'YES'
    assert columns['create_ts']['Default'] == 'CURRENT_TIMESTAMP'

    # update_ts: TIMESTAMP, NULL, ON UPDATE CURRENT_TIMESTAMP
    assert 'timestamp' in columns['update_ts']['Type']
    assert columns['update_ts']['Null'] == 'YES'
    assert columns['update_ts']['Extra'] == 'on update CURRENT_TIMESTAMP'


def test_domains_columns(db_connection):
    """Verify domains column definitions match schema.sql.

    Expected columns:
    - id: INT, PRI, AUTO_INCREMENT
    - domain_name: VARCHAR(32), NOT NULL
    - creator_fk: VARCHAR(64), NOT NULL, MUL
    - closed: TINYINT, NOT NULL, DEFAULT 0
    - sort_order: SMALLINT, NULL
    - create_ts: TIMESTAMP, NULL
    - update_ts: TIMESTAMP, NULL
    """
    with db_connection.cursor() as cur:
        cur.execute("DESCRIBE domains")
        columns = {row['Field']: row for row in cur.fetchall()}

    expected_fields = ['id', 'domain_name', 'creator_fk', 'closed', 'sort_order', 'create_ts', 'update_ts']
    assert set(columns.keys()) == set(expected_fields)

    # id: INT, PRI, AUTO_INCREMENT
    assert columns['id']['Type'] == 'int'
    assert columns['id']['Key'] == 'PRI'
    assert columns['id']['Null'] == 'NO'
    assert columns['id']['Extra'] == 'auto_increment'

    # domain_name: VARCHAR(32), NOT NULL
    assert columns['domain_name']['Type'] == 'varchar(32)'
    assert columns['domain_name']['Null'] == 'NO'

    # creator_fk: VARCHAR(64), NOT NULL, MUL
    assert columns['creator_fk']['Type'] == 'varchar(64)'
    assert columns['creator_fk']['Null'] == 'NO'
    assert columns['creator_fk']['Key'] == 'MUL'

    # closed: TINYINT, NOT NULL, DEFAULT 0
    assert columns['closed']['Type'] == 'tinyint'
    assert columns['closed']['Null'] == 'NO'
    assert columns['closed']['Default'] == '0'

    # sort_order: SMALLINT, NULL
    assert columns['sort_order']['Type'] == 'smallint'
    assert columns['sort_order']['Null'] == 'YES'

    # create_ts: TIMESTAMP, NULL
    assert 'timestamp' in columns['create_ts']['Type']
    assert columns['create_ts']['Null'] == 'YES'

    # update_ts: TIMESTAMP, NULL
    assert 'timestamp' in columns['update_ts']['Type']
    assert columns['update_ts']['Null'] == 'YES'


def test_areas_columns(db_connection):
    """Verify areas column definitions match schema.sql.

    Expected columns:
    - id: INT, PRI, AUTO_INCREMENT
    - area_name: VARCHAR(32), NOT NULL
    - domain_fk: INT, NULL, MUL
    - creator_fk: VARCHAR(64), NOT NULL, MUL
    - closed: TINYINT, NOT NULL, DEFAULT 0
    - sort_order: SMALLINT, NULL
    - sort_mode: VARCHAR(8), NOT NULL, DEFAULT 'priority'
    - create_ts: TIMESTAMP, NULL
    - update_ts: TIMESTAMP, NULL
    """
    with db_connection.cursor() as cur:
        cur.execute("DESCRIBE areas")
        columns = {row['Field']: row for row in cur.fetchall()}

    expected_fields = [
        'id', 'area_name', 'domain_fk', 'creator_fk', 'closed', 'sort_order',
        'sort_mode', 'create_ts', 'update_ts'
    ]
    assert set(columns.keys()) == set(expected_fields)

    # id: INT, PRI, AUTO_INCREMENT
    assert columns['id']['Type'] == 'int'
    assert columns['id']['Key'] == 'PRI'
    assert columns['id']['Null'] == 'NO'
    assert columns['id']['Extra'] == 'auto_increment'

    # area_name: VARCHAR(32), NOT NULL
    assert columns['area_name']['Type'] == 'varchar(32)'
    assert columns['area_name']['Null'] == 'NO'

    # domain_fk: INT, NULL, MUL
    assert columns['domain_fk']['Type'] == 'int'
    assert columns['domain_fk']['Null'] == 'YES'
    assert columns['domain_fk']['Key'] == 'MUL'

    # creator_fk: VARCHAR(64), NOT NULL, MUL
    assert columns['creator_fk']['Type'] == 'varchar(64)'
    assert columns['creator_fk']['Null'] == 'NO'
    assert columns['creator_fk']['Key'] == 'MUL'

    # closed: TINYINT, NOT NULL, DEFAULT 0
    assert columns['closed']['Type'] == 'tinyint'
    assert columns['closed']['Null'] == 'NO'
    assert columns['closed']['Default'] == '0'

    # sort_order: SMALLINT, NULL
    assert columns['sort_order']['Type'] == 'smallint'
    assert columns['sort_order']['Null'] == 'YES'

    # sort_mode: VARCHAR(8), NOT NULL, DEFAULT 'priority'
    assert columns['sort_mode']['Type'] == 'varchar(8)'
    assert columns['sort_mode']['Null'] == 'NO'
    assert columns['sort_mode']['Default'] == 'priority'

    # create_ts: TIMESTAMP, NULL
    assert 'timestamp' in columns['create_ts']['Type']
    assert columns['create_ts']['Null'] == 'YES'

    # update_ts: TIMESTAMP, NULL
    assert 'timestamp' in columns['update_ts']['Type']
    assert columns['update_ts']['Null'] == 'YES'


def test_tasks_columns(db_connection):
    """Verify tasks column definitions match schema.sql.

    Expected columns:
    - id: INT, PRI, AUTO_INCREMENT
    - priority: TINYINT(1), NOT NULL (BOOLEAN is TINYINT(1) in MySQL)
    - done: TINYINT(1), NOT NULL
    - description: VARCHAR(1024), NOT NULL
    - area_fk: INT, NULL, MUL
    - creator_fk: VARCHAR(64), NOT NULL, MUL
    - create_ts: TIMESTAMP, NULL
    - update_ts: TIMESTAMP, NULL
    - done_ts: TIMESTAMP, NULL
    - sort_order: SMALLINT, NULL
    """
    with db_connection.cursor() as cur:
        cur.execute("DESCRIBE tasks")
        columns = {row['Field']: row for row in cur.fetchall()}

    expected_fields = [
        'id', 'priority', 'done', 'description', 'area_fk', 'creator_fk',
        'create_ts', 'update_ts', 'done_ts', 'sort_order'
    ]
    assert set(columns.keys()) == set(expected_fields)

    # id: INT, PRI, AUTO_INCREMENT
    assert columns['id']['Type'] == 'int'
    assert columns['id']['Key'] == 'PRI'
    assert columns['id']['Null'] == 'NO'
    assert columns['id']['Extra'] == 'auto_increment'

    # priority: TINYINT(1), NOT NULL (MySQL BOOLEAN = TINYINT(1))
    assert 'tinyint' in columns['priority']['Type'].lower()
    assert columns['priority']['Null'] == 'NO'

    # done: TINYINT(1), NOT NULL
    assert 'tinyint' in columns['done']['Type'].lower()
    assert columns['done']['Null'] == 'NO'

    # description: VARCHAR(1024), NOT NULL
    assert columns['description']['Type'] == 'varchar(1024)'
    assert columns['description']['Null'] == 'NO'

    # area_fk: INT, NULL, MUL
    assert columns['area_fk']['Type'] == 'int'
    assert columns['area_fk']['Null'] == 'YES'
    assert columns['area_fk']['Key'] == 'MUL'

    # creator_fk: VARCHAR(64), NOT NULL, MUL
    assert columns['creator_fk']['Type'] == 'varchar(64)'
    assert columns['creator_fk']['Null'] == 'NO'
    assert columns['creator_fk']['Key'] == 'MUL'

    # create_ts: TIMESTAMP, NULL
    assert 'timestamp' in columns['create_ts']['Type']
    assert columns['create_ts']['Null'] == 'YES'

    # update_ts: TIMESTAMP, NULL
    assert 'timestamp' in columns['update_ts']['Type']
    assert columns['update_ts']['Null'] == 'YES'

    # done_ts: TIMESTAMP, NULL
    assert 'timestamp' in columns['done_ts']['Type']
    assert columns['done_ts']['Null'] == 'YES'

    # sort_order: SMALLINT, NULL
    assert columns['sort_order']['Type'] == 'smallint'
    assert columns['sort_order']['Null'] == 'YES'


def test_table_count(db_connection):
    """Verify darwin_dev database contains exactly 4 tables.

    Expected tables: profiles, domains, areas, tasks
    """
    with db_connection.cursor() as cur:
        cur.execute("SHOW TABLES")
        tables = {row['Tables_in_darwin_dev'] for row in cur.fetchall()}

    expected_tables = {'profiles', 'domains', 'areas', 'tasks'}
    assert expected_tables == tables, \
        f"Unexpected tables: {tables - expected_tables}, missing: {expected_tables - tables}"
