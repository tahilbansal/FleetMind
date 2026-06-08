import enum

class DepotStatus(str, enum.Enum):
    ACTIVE   = "active"
    INACTIVE = "inactive"
    MAINTENANCE = "maintenance"

class VehicleStatus(str, enum.Enum):
    AVAILABLE  = "available"
    EN_ROUTE   = "en_route"
    LOADING    = "loading"
    MAINTENANCE = "maintenance"
    OFFLINE    = "offline"

class DriverStatus(str, enum.Enum):
    AVAILABLE = "available"
    ON_DUTY   = "on_duty"
    OFF_DUTY  = "off_duty"
    SICK      = "sick"

class RoutePlanStatus(str, enum.Enum):
    DRAFT      = "draft"
    OPTIMIZING = "optimizing"
    ACTIVE     = "active"
    COMPLETED  = "completed"
    CANCELLED  = "cancelled"

class StopPriority(str, enum.Enum):
    HIGH   = "high"    # must be served today
    MEDIUM = "medium"  # default
    LOW    = "low"     # can slip to next day

class DisruptionType(str, enum.Enum):
    DRIVER_UNAVAILABLE = "driver_unavailable"
    ROAD_BLOCKED       = "road_blocked"
    WEATHER_ALERT      = "weather_alert"
    VEHICLE_BREAKDOWN  = "vehicle_breakdown"
    STOP_CANCELLED     = "stop_cancelled"
    TRAFFIC_DELAY      = "traffic_delay"

class DisruptionSource(str, enum.Enum):
    DISPATCHER_NL  = "dispatcher_nl"   # typed by human
    AI_MONITOR     = "ai_monitor"      # detected by disruption monitor agent
    WEBHOOK        = "webhook"         # pushed by external system

class VehicleCategory(str, enum.Enum):
    SMALL_VAN    = "small_van"
    LARGE_VAN    = "large_van"
    TRUCK_7T     = "truck_7t"
    TRUCK_15T    = "truck_15t"
    REFRIGERATED = "refrigerated"
    MOTORCYCLE   = "motorcycle"