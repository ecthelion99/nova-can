#ifndef NOVA_CAN_H
#define NOVA_CAN_H

#include <stdint.h>
#include <stdbool.h>

typedef struct NovaCAN_CANID {
    uint8_t priority;
    bool service;
    bool service_request;
    uint16_t port_id;
    uint8_t destination_id;
    uint8_t source_id;
} NovaCAN_CANID;

typedef struct NOVA_CAN_FRAME_HEADER {
    bool start_of_transfer;
    bool end_of_transfer;
    uint8_t transfer_id;
} NOVA_CAN_FRAME_HEADER;

void nova_can_print_canid_struct(NovaCAN_CANID *canid) {
    printf("CAN ID Structure:\n");
    printf("  Priority: %u\n", canid->priority);
    printf("  Service: %s\n", canid->service ? "true" : "false");
    printf("  Service Request: %s\n", canid->service_request ? "true" : "false");
    printf("  Subject ID: 0x%04X\n", canid->port_id);
    printf("  Destination ID: %u\n", canid->destination_id);
    printf("  Source ID: %u\n", canid->source_id);
}

void nova_can_print_frame_header_struct(NOVA_CAN_FRAME_HEADER *frame_header) {
    printf("Frame Header Structure:\n");
    printf("  Start of Transfer: %s\n", frame_header->start_of_transfer ? "true" : "false");
    printf("  End of Transfer: %s\n", frame_header->end_of_transfer ? "true" : "false");
    printf("  Transfer ID: %u\n", frame_header->transfer_id);
}

// Get the filter for a given node ID
// Returns 0 on success, -1 on failure
// Currently only filters for the node it of the recieving device
int nova_can_get_canid_filter(uint8_t node_id, uint32_t* filter){
    // Check if the node ID is valid
    if (node_id > 0x3F) {
        return -1;
    }
    // Set the filter to the node ID
    *filter = node_id << 7;
    return 0;
}

// get the mask
// Returns 0 on success, -1 on failure
// Currently only filters for the node so this is just static
int nova_can_get_canid_mask(uint32_t* mask){
    *mask = 0x3F << 7;
    return 0;
}

void nova_can_deserialize_canid(uint32_t canid, NovaCAN_CANID *canid_struct) {
    canid_struct->priority = (uint8_t)((canid >> 26) & 0x07);
    canid_struct->service = (bool)((canid >> 25) & 0x01);
    canid_struct->service_request = (bool)((canid >> 24) & 0x01);
    canid_struct->port_id = (uint16_t)((canid >> 14) & 0x1FF);
    canid_struct->destination_id = (uint8_t)((canid >> 7) & 0x3F);
    canid_struct->source_id = (uint8_t)(canid & 0x3F);
}

void nova_can_serialize_canid(NovaCAN_CANID* canid_struct, uint32_t *canid) {
    *canid = 0;
    *canid |= (uint32_t)(canid_struct->priority) << 26;
    *canid |= (uint32_t)(canid_struct->service) << 25;
    *canid |= (uint32_t)(canid_struct->service_request) << 24;
    *canid |= (uint32_t)(canid_struct->port_id) << 14;
    *canid |= (uint32_t)(canid_struct->destination_id) << 7;
    *canid |= (uint32_t)(canid_struct->source_id);
}

NOVA_CAN_FRAME_HEADER nova_can_deserialize_frame_header(uint8_t *frame_header) {
    NOVA_CAN_FRAME_HEADER frame_header_struct;
    frame_header_struct.start_of_transfer = (bool)((frame_header[0] >> 7) & 0x01);
    frame_header_struct.end_of_transfer = (bool)((frame_header[0] >> 6) & 0x01);
    frame_header_struct.transfer_id = (uint8_t)(frame_header[0] & 0x1F);
    return frame_header_struct;
}

uint8_t nova_can_serialize_frame_header(NOVA_CAN_FRAME_HEADER *frame_header_struct) {
    uint8_t frame_header = 0;
    frame_header |= (uint8_t)(frame_header_struct->start_of_transfer) << 7;
    frame_header |= (uint8_t)(frame_header_struct->end_of_transfer) << 6;
    frame_header |= (uint8_t)(frame_header_struct->transfer_id);    
    return frame_header;
}

#endif /* NOVA_CAN_H */