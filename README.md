# Exit Speed

This is not an officially supported Google product.

Race car telemetry with a Raspberry Pi.

This project started with a set of LEDs and a USB GPS dongle.  The goal was to
light the LEDs based on the current speed vs the fastest lap of the session.
Hence the name "Exit Speed".  Carrying a high speed on the exit of a turn is
crucial in the pursuit of faster lap times.

This mimics the behavior of the red/blue triangle in the HUD of GT Sport.
Exit Speed will display green LEDs if the car is faster and red when the car is
slower based on the car's position compared to the fastest lap of the session.

Later a DAQ device as added for measuring and logging voltage from sensors such
as the throttle position and water temperature.  In turn the data was exported
to a Timescale database which allows for real time analysis of the data Grafana.
Including lap comparison.

Example of data logged at Portland International Raceway being replayed.
https://youtu.be/2FHSHHTeZAU

## Hardware

### UBlox 8

The USB GPS dongle used is GNSS100L.  It is based on the UBlox 8 chipset which
is very well documented.  Note you'll want to bump the output rate of the device
to 10hz based on the UBX-CFG-RATE setting.  This can be done with the Ublox
window software to persist between power cycles.  There were a couple of other
settings that seem reasonable to change as well so I recommend reading the
manual.
http://canadagps.com/GNSS100L.html
https://www.u-blox.com/sites/default/files/products/documents/u-blox8-M8_ReceiverDescrProtSpec_%28UBX-13003221%29.pdf
`Bus 001 Device 007: ID 1546:01a8 U-Blox AG [u-blox 8]`

### Labjack U3

For converting analog voltages to digtial a Labjack U3 device as chosen based on
the documentation, API, examples and awesome support.  There are cheaper DAQ
devices out there however the U3 also supports high voltage readings (0-10v on
AIN-0-4).
https://labjack.com/products/u3

They also sell voltage dividers to drop high voltages down to the acceptable low
voltage range of 0-2.4v or 03.6v for the FIO4-EIO7 inputs.
https://labjack.com/accessories/ljtick-divider

It's worth noting the options for grounding the U3.  We ran a ground from the
SGND inputs.
https://labjack.com/support/datasheets/u3/hardware-description/ain/analog-input-connections/signal-powered-externally

### WBO2

The car I have came with an older WBO 2A0/2A1 device with a LD01 display for the
air fuel ratio.  Luckily the logging format of the devcie's terminal output is
well documented.  The wide band device also supports logging of 3 additional
5v sensors and 3 thermocouple inputs.
http://wbo2.com/2a0/default.htm

## Software Design Choices

Python has suprisingly been able to keep up with the GPS 10hz output.  Ideally
this should be rewritten in Go or C++.

### Crossing Start/Finish

There is a map of tracks in the NW with GPS locations of start/finish points
select from Google maps.   The ExitSpeed class is initialized with a
start_finish_range which determines how close the car needs to be to the finish
line before we consider the lap complete.  Then we look at 3 points in a row to
see if the car started to move away from the finish line.  Without the range
limit points on far ends of the track would have counted as crossing
start/finish.

### Speed Deltas (LEDs)

For the fastest lap a BallTree is constructed of GPS coordinates for the lap.
On the current lap each GPS point's speed is compared against the closest point of the best lap by searching the BallTree.  The delta of the speed of these
points are stored in a collections.deque which holds the last 50 points.  If the
median of the points are faster then the LEDs are set to green.  If slower
they're set to red.
https://scikit-learn.org/stable/modules/generated/sklearn.neighbors.BallTree.html

Another way to put it is if the median speed of the last 5 seconds is faster set
the LEDs to green.  Else red.

Earlier versions experimented with updating the LEDs more often as well as
having a ratio of LEDs lit based on the size of the speed delta.  But having
LEDs flicker all the time isn't very helpful.  Also GPS inaccuracies can lead to
misleading results.

Here is an example of the LEDs in action.
https://youtu.be/sWjJ_7Hw02U

### Grafana & Timescale

Initially Prometheus and InfluxDB were tested before settling on Timescale.
Grafana is designed for displaying time series data which is great for live or
replayed data.  However that made graph lap comparisons difficult.  Since
Timescale is backed by PostgresSQL I was able to come up with some clever
Grafana queries to overlay laps.
https://youtu.be/2FHSHHTeZAU
https://youtu.be/joWSMB6zanM