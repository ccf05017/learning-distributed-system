"""KV Store 기본 동작 테스트 (A 시나리오)"""


class TestBasicOperations:
    """A. 기본 동작(정상 시나리오)"""

    def test_put_and_get_returns_value(self):
        """A1. PUT/GET 기본
        Given: 빈 스토어
        When: PUT(k, v1) 수행 후 GET(k)
        Then: GET(k)는 v1을 반환한다
        """
        from kv_store import KVStore

        store = KVStore()
        store.put("key1", "value1")

        assert store.get("key1") == "value1"

    def test_put_overwrites_existing_value(self):
        """A2. UPDATE(덮어쓰기)
        Given: PUT(k, v1)이 완료된 스토어
        When: PUT(k, v2) 수행 후 GET(k)
        Then: GET(k)는 v2를 반환한다
        """
        from kv_store import KVStore

        store = KVStore()
        store.put("key1", "value1")
        store.put("key1", "value2")

        assert store.get("key1") == "value2"

    def test_delete_removes_key(self):
        """A3. DELETE
        Given: PUT(k, v1)이 완료된 스토어
        When: DEL(k) 수행 후 GET(k)
        Then: GET(k)는 존재하지 않음을 반환한다
        """
        from kv_store import KVStore

        store = KVStore()
        store.put("key1", "value1")
        store.delete("key1")

        assert store.get("key1") is None

    def test_multiple_keys_are_independent(self):
        """A4. 다중 키 독립성
        Given: 빈 스토어
        When: PUT(k1, v1), PUT(k2, v2) 수행
        Then: GET(k1)=v1이고 GET(k2)=v2다
        """
        from kv_store import KVStore

        store = KVStore()
        store.put("key1", "value1")
        store.put("key2", "value2")

        assert store.get("key1") == "value1"
        assert store.get("key2") == "value2"


class TestDurability:
    """B. 내구성/복구(정상 재시작)"""

    def test_data_persists_after_restart(self, tmp_path):
        """B1. 재시작 후 데이터 유지
        Given: PUT(k, v1)이 완료된 상태
        When: 프로세스를 정상 종료 후 재시작(Recovery 수행)
        Then: GET(k)는 v1을 반환한다
        """
        from kv_store import KVStore

        store = KVStore(data_dir=tmp_path)
        store.put("key1", "value1")
        store.close()

        store2 = KVStore(data_dir=tmp_path)
        assert store2.get("key1") == "value1"
