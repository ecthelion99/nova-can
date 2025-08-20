#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/types.h>
#include <sys/socket.h>
#include <sys/ioctl.h>
#include <sys/select.h>
#include <time.h>
#include <math.h>
#include <net/if.h>
#include <linux/can.h>
#include <linux/can/raw.h>

#include "motor_driver.h"

static int s = -1;

// Simple control mode for demo
typedef enum {
	MODE_CURRENT = 0,
	MODE_VELOCITY = 1,
	MODE_POSITION = 2
} ControlMode;

// Control targets (raw int16 units from command)
static volatile ControlMode control_mode = MODE_CURRENT;
static volatile int16_t target_current = 0;
static volatile int16_t target_velocity = 0;
static volatile int16_t target_position = 0;

// Integer control and plant (int16 units per tick)
// Per-tick jerk limit: maximum change in acceleration per 100 ms tick
#define JERK_PER_TICK 5
// Map current command to acceleration per tick (accel = current / ACCEL_FROM_CURRENT_DIV)
#define ACCEL_FROM_CURRENT_DIV 2
// Velocity PI gains (accel_cmd = (KP*e + KI*sum_e) >> SHIFT)
#define VEL_KP 4
#define VEL_KI 1
#define VEL_SHIFT 3
#define VEL_INT_LIM 3000
// Position P to velocity target (vel_target = (POS_KP*e) >> POS_SHIFT)
#define POS_KP 2
#define POS_SHIFT 2

static int16_t accel_q = 0;
static int16_t vel_q = 0;
static int16_t pos_q = 0;

static int16_t vel_integral = 0;
static int16_t vel_prev_error = 0;

static inline int16_t clamp_int16(int v) {
	if (v > INT16_MAX) return INT16_MAX;
	if (v < INT16_MIN) return INT16_MIN;
	return (int16_t)v;
}

// Implement the callback functions
int nova_can_motor_driver_current_command_callback(NOVA_CAN_CANID *can_id_struct, nova_dsdl_motor_driver_msg_Command_1_0 *data) {
	printf("Received Current Command: %d\n", data->value);
	control_mode = MODE_CURRENT;
	target_current = data->value;
	return 0;
}

int nova_can_motor_driver_velocity_command_callback(NOVA_CAN_CANID *can_id_struct, nova_dsdl_motor_driver_msg_Command_1_0 *data) {
	printf("Received Velocity Command: %d\n", data->value);
	control_mode = MODE_VELOCITY;
	target_velocity = data->value;
	return 0;
}


int nova_can_motor_driver_position_command_callback(NOVA_CAN_CANID *can_id_struct, nova_dsdl_motor_driver_msg_Command_1_0 *data) {
	printf("Received Position Command: %d\n", data->value);
	control_mode = MODE_POSITION;
	target_position = data->value;
	return 0;
}


int nova_can_motor_driver_set_pidconstant_callback(NOVA_CAN_CANID *can_id_struct,
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

int nova_can_motor_driver_get_pidconstant_callback(NOVA_CAN_CANID *can_id_struct,
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

int nova_can_motor_driver_send_impl(NOVA_CAN_CANID *can_id_struct, const uint8_t *data, size_t length) {
	struct ifreq ifr;
	struct sockaddr_can addr;

	if (data == NULL || length > 8) {
		return -1;
	}

	// Require socket to be initialized and bound by main()
	if (s < 0) {
		perror("send_impl: socket not initialized");
		return -1;
	}

	struct can_frame frame;
	uint32_t serialized_id = 0;
	nova_can_serialize_canid(can_id_struct, &serialized_id);
	frame.can_id = (serialized_id & CAN_EFF_MASK) | CAN_EFF_FLAG; // 29-bit extended frame
	frame.len = (uint8_t)length;
	memset(frame.data, 0, sizeof(frame.data));
	memcpy(frame.data, data, length);

	ssize_t nbytes = write(s, &frame, sizeof(struct can_frame));
	if (nbytes != (ssize_t)sizeof(struct can_frame)) {
		perror("send_impl: write");
		return -1;
	}
	return 0;
}

static void control_tick_and_publish(void) {
	// Determine desired acceleration based on current mode (all int16 units)
	int16_t desired_accel = 0;
	if (control_mode == MODE_CURRENT) {
		desired_accel = (int16_t)(target_current / ACCEL_FROM_CURRENT_DIV);
	} else if (control_mode == MODE_VELOCITY) {
		int16_t vel_error = (int16_t)(target_velocity - vel_q);
		int v_int = vel_integral + vel_error;
		if (v_int > VEL_INT_LIM) v_int = VEL_INT_LIM;
		if (v_int < -VEL_INT_LIM) v_int = -VEL_INT_LIM;
		vel_integral = (int16_t)v_int;
		int32_t acc_cmd = (int32_t)VEL_KP * vel_error + (int32_t)VEL_KI * vel_integral;
		desired_accel = (int16_t)(acc_cmd >> VEL_SHIFT);
		vel_prev_error = vel_error;
	} else { // MODE_POSITION
		int16_t pos_error = (int16_t)(target_position - pos_q);
		int16_t vel_target_from_pos = (int16_t)(((int32_t)POS_KP * pos_error) >> POS_SHIFT);
		int16_t vel_error = (int16_t)(vel_target_from_pos - vel_q);
		int v_int = vel_integral + vel_error;
		if (v_int > VEL_INT_LIM) v_int = VEL_INT_LIM;
		if (v_int < -VEL_INT_LIM) v_int = -VEL_INT_LIM;
		vel_integral = (int16_t)v_int;
		int32_t acc_cmd = (int32_t)VEL_KP * vel_error + (int32_t)VEL_KI * vel_integral;
		desired_accel = (int16_t)(acc_cmd >> VEL_SHIFT);
		vel_prev_error = vel_error;
	}

	// Jerk limit per tick
	int16_t delta_a = (int16_t)(desired_accel - accel_q);
	if (delta_a > JERK_PER_TICK) delta_a = JERK_PER_TICK;
	if (delta_a < -JERK_PER_TICK) delta_a = -JERK_PER_TICK;
	accel_q = (int16_t)(accel_q + delta_a);

	// Integrate
	vel_q = clamp_int16((int)vel_q + accel_q);
	pos_q = clamp_int16((int)pos_q + vel_q);

	// Estimate current from accel (inverse of ACCEL_FROM_CURRENT_DIV)
	int16_t current_est = clamp_int16((int)accel_q * ACCEL_FROM_CURRENT_DIV);

	// Publish telemetry directly in int16 units
	nova_dsdl_sensors_msg_Current_1_0 cur_msg; cur_msg.value = current_est;
	nova_can_motor_driver_tx(NOVA_CAN_MOTOR_DRIVER_MSG_TRANSMIT_CURRENT, &cur_msg, 4, true, 0);

	nova_dsdl_sensors_msg_Velocity_1_0 vel_msg; vel_msg.value = vel_q;
	nova_can_motor_driver_tx(NOVA_CAN_MOTOR_DRIVER_MSG_TRANSMIT_VELOCITY, &vel_msg, 4, true, 0);

	nova_dsdl_sensors_msg_Position_1_0 pos_msg; pos_msg.value = pos_q;
	nova_can_motor_driver_tx(NOVA_CAN_MOTOR_DRIVER_MSG_TRANSMIT_POSITION, &pos_msg, 4, true, 0);
}

int main(int argc, char *argv[]) {

	// Device/Microcontroller specific CAN initialization
	// In this case we need to set up socketCAN
	/* using file-scope CAN socket s */
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

	// Initialize periodic tick schedule (10 Hz)
	struct timespec next_tick;
	clock_gettime(CLOCK_MONOTONIC, &next_tick);
	next_tick.tv_nsec += 100000000L; // +100ms
	if (next_tick.tv_nsec >= 1000000000L) {
		next_tick.tv_sec += 1;
		next_tick.tv_nsec -= 1000000000L;
	}

	while (1) {
		// Compute timeout until next tick
		struct timespec now;
		clock_gettime(CLOCK_MONOTONIC, &now);
		long dsec = next_tick.tv_sec - now.tv_sec;
		long dnsec = next_tick.tv_nsec - now.tv_nsec;
		if (dnsec < 0) { dsec -= 1; dnsec += 1000000000L; }
		if (dsec < 0) { dsec = 0; dnsec = 0; } // overdue -> no wait

		struct timeval tv;
		tv.tv_sec = dsec;
		tv.tv_usec = (suseconds_t)(dnsec / 1000);

		fd_set rfds;
		FD_ZERO(&rfds);
		FD_SET(s, &rfds);

		int ret = select(s + 1, &rfds, NULL, NULL, &tv);
		if (ret > 0 && FD_ISSET(s, &rfds)) {
			// Read one CAN frame
			if (read(s, &frame, sizeof(struct can_frame)) < 0) {
				perror("Error reading CAN frame");
				// continue; fall through to tick update
			} else {
				size_t length = (size_t)frame.len;
				// pass the CAN ID and data to the NovaCAN library receive function
				if (nova_can_motor_driver_rx(&frame.can_id, frame.data, &length) != 0) {
                    perror("Error receiving message");
                };
			}
		} else if (ret < 0) {
			perror("select");
		}

		// Run ticks if due (catch-up if we were delayed)
		clock_gettime(CLOCK_MONOTONIC, &now);
		while ((now.tv_sec > next_tick.tv_sec) ||
		       (now.tv_sec == next_tick.tv_sec && now.tv_nsec >= next_tick.tv_nsec)) {
			control_tick_and_publish();
			// schedule next tick += 100ms
			next_tick.tv_nsec += 100000000L;
			if (next_tick.tv_nsec >= 1000000000L) {
				next_tick.tv_sec += 1;
				next_tick.tv_nsec -= 1000000000L;
			}
			clock_gettime(CLOCK_MONOTONIC, &now);
		}
	}

	close(s);
	return 0;
} 