#include <stdint.h>
#include <stdbool.h>

typedef struct NovaCAN_CANID {
    uint8_t priority;
    bool service;
    bool service_request;
    uint16_t subject_id;
    uint8_t destination_id;
    uint8_t source_id;
} NovaCAN_CANID;

void nova_can_deserialize_canid(uint32_t canid, NovaCAN_CANID *canid_struct) {
    canid_struct->priority = (uint8_t)((canid >> 26) & 0x07);
    canid_struct->service = (bool)((canid >> 25) & 0x01);
    canid_struct->service_request = (bool)((canid >> 24) & 0x01);
    canid_struct->subject_id = (uint16_t)((canid >> 14) & 0x1FF);
    canid_struct->destination_id = (uint8_t)((canid >> 7) & 0x3F);
    canid_struct->source_id = (uint8_t)(canid & 0x3F);
}

void nova_can_serialize_canid(NovaCAN_CANID* canid_struct, uint32_t *canid) {
    *canid = 0;
    *canid |= (uint32_t)(canid_struct->priority) << 26;
    *canid |= (uint32_t)(canid_struct->service) << 25;
    *canid |= (uint32_t)(canid_struct->service_request) << 24;
    *canid |= (uint32_t)(canid_struct->subject_id) << 14;
    *canid |= (uint32_t)(canid_struct->destination_id) << 7;
    *canid |= (uint32_t)(canid_struct->source_id);
}