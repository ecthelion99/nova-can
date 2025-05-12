#include "unity.h"
#include "../../src/c/nova_can.h"

void setUp(void) {}
void tearDown(void) {}

void test_canid_serialization_and_deserialization(void) {
    NovaCAN_CANID canid = {3, 0, 0, 52, 7, 1};
    uint32_t raw;
    nova_can_serialize_canid(&canid, &raw);

    NovaCAN_CANID parsed;
    nova_can_deserialize_canid(raw, &parsed);

    TEST_ASSERT_EQUAL_UINT8(3, parsed.priority);
    TEST_ASSERT_FALSE(parsed.service);
    TEST_ASSERT_FALSE(parsed.service_request);
    TEST_ASSERT_EQUAL_UINT16(52, parsed.subject_id);
    TEST_ASSERT_EQUAL_UINT8(7, parsed.destination_id);
    TEST_ASSERT_EQUAL_UINT8(1, parsed.source_id);
}

void test_canid_serialize(void) {
    NovaCAN_CANID canid = {3, 0, 0, 52, 7, 1};
    uint32_t raw;
    nova_can_serialize_canid(&canid, &raw);

    // Expected raw value based on the structure
    uint32_t expected_raw = (3 << 26) | (0 << 25) | (0 << 24) | (52 << 14) | (7 << 7) | 1;
    TEST_ASSERT_EQUAL_UINT32(expected_raw, raw);
}

void test_canid_deserialize(void) {
    uint32_t raw = (3 << 26) | (0 << 25) | (0 << 24) | (52 << 14) | (7 << 7) | 1;
    NovaCAN_CANID canid;
    nova_can_deserialize_canid(raw, &canid);

    TEST_ASSERT_EQUAL_UINT8(3, canid.priority);
    TEST_ASSERT_FALSE(canid.service);
    TEST_ASSERT_FALSE(canid.service_request);
    TEST_ASSERT_EQUAL_UINT16(52, canid.subject_id);
    TEST_ASSERT_EQUAL_UINT8(7, canid.destination_id);
    TEST_ASSERT_EQUAL_UINT8(1, canid.source_id);
}

int main(void) {
    UNITY_BEGIN();
    RUN_TEST(test_canid_serialization_and_deserialization);
    RUN_TEST(test_canid_serialize);
    RUN_TEST(test_canid_deserialize);
    return UNITY_END();
} 