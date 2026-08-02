import sqlite3
import pytest
from Backend.app.db.migrations import repair_network_logs_fk

def test_repair_network_logs_fk_dangling_reference(tmp_path):
    db_file = tmp_path / "test_forgeos.db"
    conn = sqlite3.connect(db_file)
    conn.executescript("""
        CREATE TABLE monitored_targets (id INTEGER PRIMARY KEY);
        CREATE TABLE network_logs (
            id INTEGER PRIMARY KEY, 
            target_id INTEGER, 
            FOREIGN KEY(target_id) REFERENCES monitored_targets_legacy(id)
        );
        INSERT INTO network_logs (id, target_id) VALUES (1, 100);
    """)
    conn.commit()
    conn.close()

    repair_network_logs_fk(str(db_file))

    conn = sqlite3.connect(db_file)
    fk_list = conn.execute("PRAGMA foreign_key_list(network_logs)").fetchall()
    assert any(fk[2] == 'monitored_targets' for fk in fk_list)
    conn.close()