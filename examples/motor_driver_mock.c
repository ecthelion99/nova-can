#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/types.h>
#include <sys/socket.h>
#include <sys/ioctl.h>
#include <net/if.h>
#include <linux/can.h>
#include <linux/can/raw.h>

#include "motor_driver.h"

// Implement the callback functions
int nova_can_motor_driver_current_command_callback(NovaCAN_CANID *can_id_struct, nova_dsdl_motor_driver_msg_Command_1_0 *data) {
        printf("Received Current Command: %d\n", data->value);
    return 0;
}

int nova_can_motor_driver_velocity_command_callback(NovaCAN_CANID *can_id_struct, nova_dsdl_motor_driver_msg_Command_1_0 *data) {
    printf("Received Velocity Command: %d\n", data->value);
    return 0;
}


int nova_can_motor_driver_position_command_callback(NovaCAN_CANID *can_id_struct, nova_dsdl_motor_driver_msg_Command_1_0 *data) {
    printf("Received Position Command: %d\n", data->value);
    return 0;
}


int nova_can_motor_driver_set_pidconstant_callback(NovaCAN_CANID *can_id_struct,
                                                   nova_dsdl_motor_driver_srv_SetPIDConstant_Request_1_0 *data) {
    char *constant;
    switch (data->constant) {
        case nova_dsdl_motor_driver_srv_SetPIDConstant_Request_1_0_P:
            constant = "P";
            break;
        case nova_dsdl_motor_driver_srv_SetPIDConstant_Request_1_0_I:
            constant = "I";
            break;
        case nova_dsdl_motor_driver_srv_SetPIDConstant_Request_1_0_D:
            constant = "D";
            break;
        default:
            constant = "UNKNOWN";
            break;
    }
    printf("Received SetPIDConstant Request:\n    CONST: %s\n    VALUE: %4X\n", constant, data->value);
    // We would then need to send a response back to the sender
    // but ncc has not implemented message sending yet
    return 0;
}

int nova_can_motor_driver_get_pidconstant_callback(NovaCAN_CANID *can_id_struct,
                                                   nova_dsdl_motor_driver_srv_GetPIDConstant_Request_1_0 *data) {
    char *constant;
    switch (data->constant) {
        case nova_dsdl_motor_driver_srv_GetPIDConstant_Request_1_0_P:
            constant = "P";
            break;
        case nova_dsdl_motor_driver_srv_GetPIDConstant_Request_1_0_I:
            constant = "I";
            break;
        case nova_dsdl_motor_driver_srv_GetPIDConstant_Request_1_0_D:
            constant = "D";
            break;
        default:
            constant = "UNKNOWN";
            break;
    }
    printf("Received GetPIDConstant Request: CONST: %s\n", constant);
    // We would then need to send a response back to the sender
    // but ncc has not implemented message sending yet
    return 0;
}

int main(int argc, char *argv[]) {

    // Device/Microcontroller specific CAN initialization
    // In this case we need to set up socketCAN
    int s;
    struct sockaddr_can addr;
    struct ifreq ifr;
    struct can_frame frame;

    // Create socket
    if ((s = socket(PF_CAN, SOCK_RAW, CAN_RAW)) < 0) {
        perror("Error creating socket");
        return 1;
    }

    // Get interface index
    strncpy(ifr.ifr_name, "can0", IF_NAMESIZE - 1);
    ifr.ifr_name[IF_NAMESIZE - 1] = '\0';  // Ensure null termination

    if (ioctl(s, SIOCGIFINDEX, &ifr) < 0) {
        perror("Error getting interface index");
        return 1;
    }

    // Bind socket to interface
    addr.can_family = AF_CAN;
    addr.can_ifindex = ifr.ifr_ifindex;
    if (bind(s, (struct sockaddr *)&addr, sizeof(addr)) < 0) {
        perror("Error binding socket");
        return 1;
    }

    // Currently no library initialization is needed
    // in the future there will be an init function
    // taking the NODE_ID. This will be used for
    // creating tx msgs and CANID filters/masks
    if (argc != 2) {
        printf("Usage: %s <node_id>\n", argv[0]);
        return 1;
    }
    uint32_t const NODE_ID = (uint32_t)atoi(argv[1]);
    if (NODE_ID > 0xFF || NODE_ID < 1) {
        printf("Error: node_id must be between 1 and 127\n");
        return 1;
    }

    // Auto-generated filter/mask are not currently
    // implemented, so we need to manually set them
    // For now we will just filter out the node ID

    uint32_t filter;
    uint32_t mask;
    nova_can_get_canid_filter(NODE_ID, &filter);
    nova_can_get_canid_mask(&mask);

    // Now we set the filter and mask
    // for the specific Device/Microcontroller
    // in this case with socketCAN
    struct can_filter rfilter[1];
    rfilter[0].can_id = filter;
    rfilter[0].can_mask = mask;
    if (setsockopt(s, SOL_CAN_RAW, CAN_RAW_FILTER, &rfilter, sizeof(rfilter)) < 0) {
        perror("Error setting socket options");
        return 1;
    }

    while (1) {
        // Read CAN frame
        if (read(s, &frame, sizeof(struct can_frame)) < 0) {
            perror("Error reading CAN frame");
            continue;
        }

        size_t length = (size_t)frame.len;

        // pass the CAN ID and data to the NovaCAN library receive function
        nova_can_motor_driver_rx(&frame.can_id, frame.data, &length);
    }

    close(s);
    return 0;
} 