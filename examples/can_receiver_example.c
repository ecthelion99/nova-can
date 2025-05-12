#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <net/if.h>
#include <sys/socket.h>
#include <linux/can.h>
#include <linux/can/raw.h>
#include "../src/c/nova_can.h"
#include <sys/ioctl.h>

void print_canid_struct(NovaCAN_CANID *canid) {
    printf("CAN ID Structure:\n");
    printf("  Priority: %u\n", canid->priority);
    printf("  Service: %s\n", canid->service ? "true" : "false");
    printf("  Service Request: %s\n", canid->service_request ? "true" : "false");
    printf("  Subject ID: 0x%04X\n", canid->subject_id);
    printf("  Destination ID: %u\n", canid->destination_id);
    printf("  Source ID: %u\n", canid->source_id);
}

int main(int argc, char *argv[]) {
    int s;
    struct sockaddr_can addr;
    struct ifreq ifr;
    struct can_frame frame;
    NovaCAN_CANID canid_struct;

    if (argc != 2) {
        printf("Usage: %s <can_interface>\n", argv[0]);
        printf("Example: %s can0\n", argv[0]);
        return 1;
    }

    // Create socket
    if ((s = socket(PF_CAN, SOCK_RAW, CAN_RAW)) < 0) {
        perror("Error creating socket");
        return 1;
    }

    // Get interface index
    strcpy(ifr.ifr_name, argv[1]);
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

    printf("Listening for CAN messages on %s...\n", argv[1]);

    while (1) {
        // Read CAN frame
        if (read(s, &frame, sizeof(struct can_frame)) < 0) {
            perror("Error reading CAN frame");
            continue;
        }

        // Parse CAN ID
        nova_can_deserialize_canid(frame.can_id, &canid_struct);

        // Print received data
        printf("\nReceived CAN Frame:\n");
        printf("CAN ID: 0x%X\n", frame.can_id);
        printf("DLC: %d\n", frame.can_dlc);
        printf("Data: ");
        for (int i = 0; i < frame.can_dlc; i++) {
            printf("%02X ", frame.data[i]);
        }
        printf("\n");

        // Print parsed CAN ID structure
        print_canid_struct(&canid_struct);
    }

    close(s);
    return 0;
} 