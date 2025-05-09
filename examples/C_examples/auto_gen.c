#include "nova_can_motor_driver.h"

int motor_driver_command_callback(nova_motor_driver_Command_1_0 *command) {
    switch (command->mode){
        case nova_motor_driver_Command_1_0_CURRENT:
            drive_current(command->value);
        case nova_motor_driver_Command_1_0_VELOCITY:
            drive_velocity(command->value);
        case nova_motor_driver_Command_1_0_CURRENT:
            drive_position(command->value);
    }
}

int main() {

    NovaCAN nova_can = nova_can_init(
        1           //Node ID
    );

    uint32_t mask = nova_can_generate_id_mask(&nova_can);
    uint32_t filter = nova_can_generate_id_filter(&nova_can);

    //hardware specific code to add mask and filter here.

    while(true) {
        // hardware specific code to get can messages
        ...
        // process the recieved message
        nova_can_proccess_rx(&nova_can, //pointer to the nova_can struct
                             *can_id,   //pointer to the can_id
                             *data_buff,//pointer to the can data buffer
                             data_length, // length of the data
        )
    }

    return 1;
}