BOOKING_TRANSITIONS={'Confirmed':{'Checked-In','Cancelled'},'Checked-In':{'Checked-Out'}}
SERVICE_REQUEST_TRANSITIONS={'New':{'Pending','In Progress','Cancelled'},'Pending':{'In Progress','Cancelled'},'In Progress':{'Pending','Completed'},'Completed':set(),'Cancelled':set()}

def booking_transition_allowed(current,new):
    return new in BOOKING_TRANSITIONS.get(current,set())

def service_request_transition_allowed(current,new):
    return new in SERVICE_REQUEST_TRANSITIONS.get(current,set())
