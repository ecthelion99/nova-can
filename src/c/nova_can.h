#ifndef NOVA_CAN_H
#define NOVA_CAN_H

#include <stdint.h>
#include <stdbool.h>

typedef struct NOVA_CAN_CANID {
    uint8_t priority;
    bool service;
    bool service_request;
    uint16_t port_id;
    uint8_t destination_id;
    uint8_t source_id;
} NOVA_CAN_CANID;

typedef struct NOVA_CAN_FRAME_HEADER {
    bool start_of_transfer;
    bool end_of_transfer;
    uint8_t transfer_id;
} NOVA_CAN_FRAME_HEADER;

static inline void nova_can_deserialize_canid(uint32_t canid, NOVA_CAN_CANID *canid_struct) {
    canid_struct->priority = (uint8_t)((canid >> 26) & 0x07);
    canid_struct->service = (bool)((canid >> 25) & 0x01);
    canid_struct->service_request = (bool)((canid >> 24) & 0x01);
    canid_struct->port_id = (uint16_t)((canid >> 14) & 0x1FF);
    canid_struct->destination_id = (uint8_t)((canid >> 7) & 0x3F);
    canid_struct->source_id = (uint8_t)(canid & 0x3F);
}

static inline void nova_can_serialize_canid(NOVA_CAN_CANID* canid_struct, uint32_t *canid) {
    *canid = 0;
    *canid |= (uint32_t)(canid_struct->priority) << 26;
    *canid |= (uint32_t)(canid_struct->service) << 25;
    *canid |= (uint32_t)(canid_struct->service_request) << 24;
    *canid |= (uint32_t)(canid_struct->port_id) << 14;
    *canid |= (uint32_t)(canid_struct->destination_id) << 7;
    *canid |= (uint32_t)(canid_struct->source_id);
}

static inline NOVA_CAN_FRAME_HEADER nova_can_deserialize_frame_header(uint8_t *frame_header) {
    NOVA_CAN_FRAME_HEADER frame_header_struct;
    frame_header_struct.start_of_transfer = (bool)((frame_header[0] >> 7) & 0x01);
    frame_header_struct.end_of_transfer = (bool)((frame_header[0] >> 6) & 0x01);
    frame_header_struct.transfer_id = (uint8_t)(frame_header[0] & 0x1F);
    return frame_header_struct;
}

static inline uint8_t nova_can_serialize_frame_header(NOVA_CAN_FRAME_HEADER *frame_header_struct) {
    uint8_t frame_header = 0;
    frame_header |= (uint8_t)(frame_header_struct->start_of_transfer) << 7;
    frame_header |= (uint8_t)(frame_header_struct->end_of_transfer) << 6;
    frame_header |= (uint8_t)(frame_header_struct->transfer_id);    
    return frame_header;
}

#endif /* NOVA_CAN_H */