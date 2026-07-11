from enum import Enum

class InterfaceType(Enum):
    POSITION = 1
    VELOCITY = 2
    EFFORT = 3
    
class GoalSpace(Enum):
    JS = 1
    TS = 2
    
class MoveStatus(Enum):
    IDLE = 1
    MOVING = 2
    BRAKE = 3
    ERROR = 4
    ODRIVE_ERROR = 5