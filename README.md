# PantryBrain
This is a part of my broader smart pantry project Rikōtodana. This is currently in the prototype stage.
It provides the services that manage the inventory based on the signals that come from the associated sensors (PantrySense).
It also provides a REST-API for the smartphone app (PantryControl).

To get started, you need to rename the `smrtfood-example.db` in the `db` folder to `smrtfood.db`.
Then you need to run both `run_statemach.py` and `run_webservice.py` in the background (for example with the GNU tool `screen`).
Since this project relies on an MQTT broker, you need to set one up and change the credentials and broker address in `core/statemachine_mqtt.json`.

`fetch_recalls.py` needs to be executed every night. On Linux, you can do that with the `crontab` tool.
An example crontab entry that runs it every night at 4 a.m.:  
`0 4 * * *       /usr/bin/python3 /path/to/software/fetch_recalls.py`

### Security warning
Since this is still a prototype, many security measures are missing! Transport encryption for both the REST-API and the MQTT messages have not been implemented yet. Authentication and authorization techniques for the REST-API are also not implemented. TL;DR: This is a prototype without any security (yet).
