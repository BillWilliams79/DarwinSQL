"""
Test data type definitions and schema correctness.

Verifies that DESCRIBE output for each table matches the expected schema.sql
definitions. Uses darwin_dev test database (profiles, domains, areas, tasks).
"""


def test_profiles_columns(db_connection):
    """Verify profiles column definitions match schema.sql.

    Expected columns (post migration 015 slim-down):
    - id: VARCHAR(64), PRI, NOT NULL
    - name: VARCHAR(256), NOT NULL
    - email: VARCHAR(256), NOT NULL
    - timezone: VARCHAR(64), NULL
    - create_ts: TIMESTAMP, NULL, DEFAULT CURRENT_TIMESTAMP
    - update_ts: TIMESTAMP, NULL, ON UPDATE CURRENT_TIMESTAMP
    """
    with db_connection.cursor() as cur:
        cur.execute("DESCRIBE profiles")
        columns = {row['Field']: row for row in cur.fetchall()}

    # Verify all expected columns exist
    expected_fields = ['id', 'name', 'email', 'timezone', 'create_ts', 'update_ts']
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

    # timezone: VARCHAR(64), NULL
    assert columns['timezone']['Type'] == 'varchar(64)'
    assert columns['timezone']['Null'] == 'YES'

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
        'create_ts', 'update_ts', 'done_ts', 'sort_order', 'recurring_task_fk'
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

    # recurring_task_fk: INT, NULL, MUL
    assert columns['recurring_task_fk']['Type'] == 'int'
    assert columns['recurring_task_fk']['Null'] == 'YES'
    assert columns['recurring_task_fk']['Key'] == 'MUL'


def test_projects_columns(db_connection):
    """Verify projects column definitions match schema.sql.

    Expected columns:
    - id: INT, PRI, AUTO_INCREMENT
    - project_name: VARCHAR(128), NOT NULL
    - creator_fk: VARCHAR(64), NOT NULL, MUL
    - sort_order: SMALLINT, NULL
    - closed: TINYINT(1), NOT NULL, DEFAULT 0
    - create_ts: TIMESTAMP, NULL, DEFAULT CURRENT_TIMESTAMP
    - update_ts: TIMESTAMP, NULL, ON UPDATE CURRENT_TIMESTAMP
    """
    with db_connection.cursor() as cur:
        cur.execute("DESCRIBE projects")
        columns = {row['Field']: row for row in cur.fetchall()}

    expected_fields = ['id', 'project_name', 'creator_fk', 'sort_order', 'closed',
                       'create_ts', 'update_ts']
    assert set(columns.keys()) == set(expected_fields)

    assert columns['id']['Type'] == 'int'
    assert columns['id']['Key'] == 'PRI'
    assert columns['id']['Extra'] == 'auto_increment'

    assert columns['project_name']['Type'] == 'varchar(128)'
    assert columns['project_name']['Null'] == 'NO'

    assert columns['creator_fk']['Type'] == 'varchar(64)'
    assert columns['creator_fk']['Null'] == 'NO'
    assert columns['creator_fk']['Key'] == 'MUL'

    assert columns['sort_order']['Type'] == 'smallint'
    assert columns['sort_order']['Null'] == 'YES'

    assert 'tinyint' in columns['closed']['Type']
    assert columns['closed']['Null'] == 'NO'
    assert columns['closed']['Default'] == '0'

    assert 'timestamp' in columns['create_ts']['Type']
    assert columns['create_ts']['Default'] == 'CURRENT_TIMESTAMP'

    assert 'timestamp' in columns['update_ts']['Type']
    assert columns['update_ts']['Extra'] == 'on update CURRENT_TIMESTAMP'


def test_categories_columns(db_connection):
    """Verify categories column definitions match schema.sql.

    Expected columns:
    - id: INT, PRI, AUTO_INCREMENT
    - category_name: VARCHAR(128), NOT NULL
    - project_fk: INT, NOT NULL, MUL
    - creator_fk: VARCHAR(64), NOT NULL, MUL
    - sort_order: SMALLINT, NULL
    - sort_mode: VARCHAR(8), NOT NULL, DEFAULT 'priority'
    - closed: TINYINT(1), NOT NULL, DEFAULT 0
    - create_ts: TIMESTAMP, NULL
    - update_ts: TIMESTAMP, NULL
    """
    with db_connection.cursor() as cur:
        cur.execute("DESCRIBE categories")
        columns = {row['Field']: row for row in cur.fetchall()}

    expected_fields = ['id', 'category_name', 'project_fk', 'creator_fk',
                       'sort_order', 'sort_mode', 'closed', 'create_ts', 'update_ts']
    assert set(columns.keys()) == set(expected_fields)

    assert columns['id']['Type'] == 'int'
    assert columns['id']['Key'] == 'PRI'
    assert columns['id']['Extra'] == 'auto_increment'

    assert columns['category_name']['Type'] == 'varchar(128)'
    assert columns['category_name']['Null'] == 'NO'

    assert columns['project_fk']['Type'] == 'int'
    assert columns['project_fk']['Null'] == 'NO'
    assert columns['project_fk']['Key'] == 'MUL'

    assert columns['creator_fk']['Type'] == 'varchar(64)'
    assert columns['creator_fk']['Null'] == 'NO'
    assert columns['creator_fk']['Key'] == 'MUL'

    assert columns['sort_order']['Type'] == 'smallint'
    assert columns['sort_order']['Null'] == 'YES'

    assert columns['sort_mode']['Type'] == 'varchar(8)'
    assert columns['sort_mode']['Null'] == 'NO'
    assert columns['sort_mode']['Default'] == 'priority'

    assert 'tinyint' in columns['closed']['Type']
    assert columns['closed']['Null'] == 'NO'
    assert columns['closed']['Default'] == '0'


def test_priorities_columns(db_connection):
    """Verify priorities column definitions match schema.sql.

    Expected columns:
    - id: INT, PRI, AUTO_INCREMENT
    - title: VARCHAR(256), NOT NULL
    - description: TEXT, NULL
    - in_progress: TINYINT(1), NOT NULL, DEFAULT 0
    - closed: TINYINT(1), NOT NULL, DEFAULT 0
    - started_at: TIMESTAMP, NULL
    - completed_at: TIMESTAMP, NULL
    - project_fk: INT, NULL, MUL
    - category_fk: INT, NULL, MUL
    - creator_fk: VARCHAR(64), NOT NULL, MUL
    - sort_order: SMALLINT, NULL
    - create_ts: TIMESTAMP, NULL
    - update_ts: TIMESTAMP, NULL
    - scheduled: TINYINT, NOT NULL, DEFAULT 0
    """
    with db_connection.cursor() as cur:
        cur.execute("DESCRIBE priorities")
        columns = {row['Field']: row for row in cur.fetchall()}

    expected_fields = ['id', 'title', 'description', 'in_progress', 'closed',
                       'started_at', 'completed_at', 'project_fk', 'category_fk',
                       'creator_fk', 'sort_order', 'create_ts', 'update_ts', 'scheduled']
    assert set(columns.keys()) == set(expected_fields)

    assert columns['id']['Type'] == 'int'
    assert columns['id']['Key'] == 'PRI'
    assert columns['id']['Extra'] == 'auto_increment'

    assert columns['title']['Type'] == 'varchar(256)'
    assert columns['title']['Null'] == 'NO'

    assert columns['description']['Type'] == 'text'
    assert columns['description']['Null'] == 'YES'

    assert 'tinyint' in columns['in_progress']['Type']
    assert columns['in_progress']['Null'] == 'NO'
    assert columns['in_progress']['Default'] == '0'

    assert 'tinyint' in columns['closed']['Type']
    assert columns['closed']['Null'] == 'NO'
    assert columns['closed']['Default'] == '0'

    assert 'timestamp' in columns['started_at']['Type']
    assert columns['started_at']['Null'] == 'YES'

    assert 'timestamp' in columns['completed_at']['Type']
    assert columns['completed_at']['Null'] == 'YES'

    assert columns['project_fk']['Type'] == 'int'
    assert columns['project_fk']['Null'] == 'YES'
    assert columns['project_fk']['Key'] == 'MUL'

    assert columns['category_fk']['Type'] == 'int'
    assert columns['category_fk']['Null'] == 'YES'
    assert columns['category_fk']['Key'] == 'MUL'

    assert columns['creator_fk']['Type'] == 'varchar(64)'
    assert columns['creator_fk']['Null'] == 'NO'
    assert columns['creator_fk']['Key'] == 'MUL'

    assert columns['sort_order']['Type'] == 'smallint'
    assert columns['sort_order']['Null'] == 'YES'

    assert 'tinyint' in columns['scheduled']['Type']
    assert columns['scheduled']['Null'] == 'NO'
    assert columns['scheduled']['Default'] == '0'


def test_swarm_sessions_columns(db_connection):
    """Verify swarm_sessions column definitions match schema.sql.

    Expected columns:
    - id: INT, PRI, AUTO_INCREMENT
    - branch: VARCHAR(128), NULL
    - task_name: VARCHAR(128), NULL
    - source_type: VARCHAR(16), NULL
    - source_ref: VARCHAR(64), NULL
    - title: VARCHAR(256), NULL
    - pr_url: VARCHAR(512), NULL
    - swarm_status: VARCHAR(16), NOT NULL, DEFAULT 'starting'
    - worktree_path: VARCHAR(512), NULL
    - started_at: TIMESTAMP, NULL
    - completed_at: TIMESTAMP, NULL
    - creator_fk: VARCHAR(64), NOT NULL, MUL
    - create_ts: TIMESTAMP, NULL
    - update_ts: TIMESTAMP, NULL
    """
    with db_connection.cursor() as cur:
        cur.execute("DESCRIBE swarm_sessions")
        columns = {row['Field']: row for row in cur.fetchall()}

    expected_fields = ['id', 'branch', 'task_name', 'source_type', 'source_ref',
                       'title', 'pr_url', 'swarm_status', 'worktree_path',
                       'started_at', 'completed_at', 'creator_fk', 'create_ts', 'update_ts']
    assert set(columns.keys()) == set(expected_fields)

    assert columns['id']['Type'] == 'int'
    assert columns['id']['Key'] == 'PRI'
    assert columns['id']['Extra'] == 'auto_increment'

    assert columns['branch']['Type'] == 'varchar(128)'
    assert columns['branch']['Null'] == 'YES'

    assert columns['task_name']['Type'] == 'varchar(128)'
    assert columns['task_name']['Null'] == 'YES'

    assert columns['source_type']['Type'] == 'varchar(16)'
    assert columns['source_type']['Null'] == 'YES'

    assert columns['source_ref']['Type'] == 'varchar(64)'
    assert columns['source_ref']['Null'] == 'YES'

    assert columns['title']['Type'] == 'varchar(256)'
    assert columns['title']['Null'] == 'YES'

    assert columns['pr_url']['Type'] == 'varchar(512)'
    assert columns['pr_url']['Null'] == 'YES'

    assert columns['swarm_status']['Type'] == 'varchar(16)'
    assert columns['swarm_status']['Null'] == 'NO'
    assert columns['swarm_status']['Default'] == 'starting'

    assert columns['worktree_path']['Type'] == 'varchar(512)'
    assert columns['worktree_path']['Null'] == 'YES'

    assert columns['creator_fk']['Type'] == 'varchar(64)'
    assert columns['creator_fk']['Null'] == 'NO'
    assert columns['creator_fk']['Key'] == 'MUL'


def test_priority_sessions_columns(db_connection):
    """Verify priority_sessions column definitions match schema.sql.

    Expected columns:
    - priority_fk: INT, PRI, NOT NULL
    - session_fk: INT, PRI, NOT NULL
    """
    with db_connection.cursor() as cur:
        cur.execute("DESCRIBE priority_sessions")
        columns = {row['Field']: row for row in cur.fetchall()}

    expected_fields = ['priority_fk', 'session_fk']
    assert set(columns.keys()) == set(expected_fields)

    assert columns['priority_fk']['Type'] == 'int'
    assert columns['priority_fk']['Null'] == 'NO'
    assert columns['priority_fk']['Key'] == 'PRI'

    assert columns['session_fk']['Type'] == 'int'
    assert columns['session_fk']['Null'] == 'NO'
    assert columns['session_fk']['Key'] == 'PRI'


def test_dev_servers_columns(db_connection):
    """Verify dev_servers column definitions match schema.sql.

    Expected columns:
    - id: INT, PRI, AUTO_INCREMENT
    - port: SMALLINT, NOT NULL, UNI
    - pid: INT, NOT NULL
    - workspace_path: VARCHAR(512), NOT NULL
    - session_fk: INT, NULL, MUL
    - creator_fk: VARCHAR(64), NOT NULL, MUL
    - started_at: TIMESTAMP, NOT NULL
    - create_ts: TIMESTAMP, NULL
    - update_ts: TIMESTAMP, NULL
    """
    with db_connection.cursor() as cur:
        cur.execute("DESCRIBE dev_servers")
        columns = {row['Field']: row for row in cur.fetchall()}

    expected_fields = ['id', 'port', 'pid', 'workspace_path', 'session_fk',
                       'creator_fk', 'started_at', 'create_ts', 'update_ts']
    assert set(columns.keys()) == set(expected_fields)

    assert columns['id']['Type'] == 'int'
    assert columns['id']['Key'] == 'PRI'
    assert columns['id']['Extra'] == 'auto_increment'

    assert columns['port']['Type'] == 'smallint'
    assert columns['port']['Null'] == 'NO'
    assert columns['port']['Key'] == 'UNI'

    assert columns['pid']['Type'] == 'int'
    assert columns['pid']['Null'] == 'NO'

    assert columns['workspace_path']['Type'] == 'varchar(512)'
    assert columns['workspace_path']['Null'] == 'NO'

    assert columns['session_fk']['Type'] == 'int'
    assert columns['session_fk']['Null'] == 'YES'
    assert columns['session_fk']['Key'] == 'MUL'

    assert columns['creator_fk']['Type'] == 'varchar(64)'
    assert columns['creator_fk']['Null'] == 'NO'
    assert columns['creator_fk']['Key'] == 'MUL'

    assert 'timestamp' in columns['started_at']['Type']
    assert columns['started_at']['Null'] == 'NO'


def test_priority_card_order_columns(db_connection):
    """Verify priority_card_order column definitions match schema.sql.

    Expected columns:
    - id: INT, PRI, AUTO_INCREMENT
    - domain_id: INT, NOT NULL, MUL (part of UNIQUE)
    - task_id: INT, NOT NULL
    - sort_order: SMALLINT, NOT NULL
    """
    with db_connection.cursor() as cur:
        cur.execute("DESCRIBE priority_card_order")
        columns = {row['Field']: row for row in cur.fetchall()}

    expected_fields = ['id', 'domain_id', 'task_id', 'sort_order']
    assert set(columns.keys()) == set(expected_fields)

    assert columns['id']['Type'] == 'int'
    assert columns['id']['Key'] == 'PRI'
    assert columns['id']['Extra'] == 'auto_increment'

    assert columns['domain_id']['Type'] == 'int'
    assert columns['domain_id']['Null'] == 'NO'
    assert columns['domain_id']['Key'] == 'MUL'

    assert columns['task_id']['Type'] == 'int'
    assert columns['task_id']['Null'] == 'NO'

    assert columns['sort_order']['Type'] == 'smallint'
    assert columns['sort_order']['Null'] == 'NO'


def test_recurring_tasks_columns(db_connection):
    """Verify recurring_tasks column definitions match schema.sql.

    Expected columns (migration 017):
    - id: INT, PRI, AUTO_INCREMENT
    - description: VARCHAR(1024), NOT NULL
    - recurrence: VARCHAR(16), NOT NULL
    - anchor_date: DATE, NOT NULL
    - area_fk: INT, NOT NULL, MUL
    - priority: TINYINT(1), NOT NULL, DEFAULT 0
    - accumulate: TINYINT(1), NOT NULL, DEFAULT 1
    - insert_position: VARCHAR(8), NOT NULL, DEFAULT 'bottom'
    - active: TINYINT(1), NOT NULL, DEFAULT 1
    - last_generated: DATE, NULL
    - creator_fk: VARCHAR(64), NOT NULL, MUL
    - create_ts: TIMESTAMP, NULL, DEFAULT CURRENT_TIMESTAMP
    - update_ts: TIMESTAMP, NULL, ON UPDATE CURRENT_TIMESTAMP
    """
    with db_connection.cursor() as cur:
        cur.execute("DESCRIBE recurring_tasks")
        columns = {row['Field']: row for row in cur.fetchall()}

    expected_fields = [
        'id', 'description', 'recurrence', 'anchor_date', 'area_fk',
        'priority', 'accumulate', 'insert_position', 'active',
        'last_generated', 'creator_fk', 'create_ts', 'update_ts'
    ]
    assert set(columns.keys()) == set(expected_fields), \
        f"Unexpected columns: {set(columns.keys()) - set(expected_fields)}"

    # id: INT, PRI, AUTO_INCREMENT
    assert columns['id']['Type'] == 'int'
    assert columns['id']['Key'] == 'PRI'
    assert columns['id']['Null'] == 'NO'
    assert columns['id']['Extra'] == 'auto_increment'

    # description: VARCHAR(1024), NOT NULL
    assert columns['description']['Type'] == 'varchar(1024)'
    assert columns['description']['Null'] == 'NO'

    # recurrence: VARCHAR(16), NOT NULL
    assert columns['recurrence']['Type'] == 'varchar(16)'
    assert columns['recurrence']['Null'] == 'NO'

    # anchor_date: DATE, NOT NULL
    assert columns['anchor_date']['Type'] == 'date'
    assert columns['anchor_date']['Null'] == 'NO'

    # area_fk: INT, NOT NULL, MUL
    assert columns['area_fk']['Type'] == 'int'
    assert columns['area_fk']['Null'] == 'NO'
    assert columns['area_fk']['Key'] == 'MUL'

    # priority: TINYINT(1), NOT NULL, DEFAULT 0
    assert 'tinyint' in columns['priority']['Type'].lower()
    assert columns['priority']['Null'] == 'NO'
    assert columns['priority']['Default'] == '0'

    # accumulate: TINYINT(1), NOT NULL, DEFAULT 1
    assert 'tinyint' in columns['accumulate']['Type'].lower()
    assert columns['accumulate']['Null'] == 'NO'
    assert columns['accumulate']['Default'] == '1'

    # insert_position: VARCHAR(8), NOT NULL, DEFAULT 'bottom'
    assert columns['insert_position']['Type'] == 'varchar(8)'
    assert columns['insert_position']['Null'] == 'NO'
    assert columns['insert_position']['Default'] == 'bottom'

    # active: TINYINT(1), NOT NULL, DEFAULT 1
    assert 'tinyint' in columns['active']['Type'].lower()
    assert columns['active']['Null'] == 'NO'
    assert columns['active']['Default'] == '1'

    # last_generated: DATE, NULL
    assert columns['last_generated']['Type'] == 'date'
    assert columns['last_generated']['Null'] == 'YES'

    # creator_fk: VARCHAR(64), NOT NULL, MUL
    assert columns['creator_fk']['Type'] == 'varchar(64)'
    assert columns['creator_fk']['Null'] == 'NO'
    assert columns['creator_fk']['Key'] == 'MUL'

    # create_ts: TIMESTAMP, NULL, DEFAULT CURRENT_TIMESTAMP
    assert 'timestamp' in columns['create_ts']['Type']
    assert columns['create_ts']['Null'] == 'YES'
    assert columns['create_ts']['Default'] == 'CURRENT_TIMESTAMP'

    # update_ts: TIMESTAMP, NULL, ON UPDATE CURRENT_TIMESTAMP
    assert 'timestamp' in columns['update_ts']['Type']
    assert columns['update_ts']['Null'] == 'YES'
    assert columns['update_ts']['Extra'] == 'on update CURRENT_TIMESTAMP'


def test_table_count(db_connection):
    """Verify darwin_dev database contains all 12 expected tables."""
    with db_connection.cursor() as cur:
        cur.execute("SHOW TABLES")
        tables = {row['Tables_in_darwin_dev'] for row in cur.fetchall()}

    expected_tables = {
        'profiles', 'domains', 'areas', 'recurring_tasks', 'tasks',
        'projects', 'categories', 'priorities', 'priority_sessions',
        'swarm_sessions', 'dev_servers', 'priority_card_order',
    }
    assert expected_tables == tables, \
        f"Unexpected tables: {tables - expected_tables}, missing: {expected_tables - tables}"
