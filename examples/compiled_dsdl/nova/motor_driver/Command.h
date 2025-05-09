

#define CURRENT 0

#define VELOCITY 1

#define POSITION 3


typedef struct nova_motor_driver_Command {

    saturated int2 mode;

    saturated int16 value;

} nova_motor_driver_Command;