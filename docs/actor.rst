.. _actor:

Actor
=====

``basecam`` includes a default implementation of an SDSS-style ``actor`` to provide an interface for the camera system. An :ref:`actor <clu:getting-started>` is just a server of some kind (TCP/IP or other) that accepts commands directed to the camera system, performs the commanded action, and replies to the user. ``basecam`` uses `CLU <https://clu.readthedocs.io/en/latest/index.html>`__ to provide the actor functionality.

The default actor implementation uses a `JSON actor <clu.actor.JSONActor>` that receives commands that resemble Unix terminal line commands and replies with a JSON object. Creating an actor for a given camera system is easy ::

    from basecam.actor import CameraActor

    class Actor(CameraActor):
        pass

    host = 'localhost'
    port = 8888
    camera_system = CameraSystem()
    actor = Actor(camera_system, host=host, port=port)
    await actor.setup()
    await actor.serve_forever()

``camera_system`` must be an instantiated camera system. At this point the actor will be running on port 8888 of localhost and a client can connect to it over telnet or open a socket and issue commands. ::

    $ telnet 127.0.0.1 8888
    status
    {
    "header": {
        "command_id": 0,
        "commander_id": "8a278303-19bc-4d3b-ba33-a0fc33fdb267",
        "message_code": ">",
        "sender": "flicamera"
    },
    "data": {}
    }
    {
        "header": {
            "command_id": 0,
            "commander_id": "8a278303-19bc-4d3b-ba33-a0fc33fdb267",
            "message_code": "i",
            "sender": "flicamera"
        },
        "data": {
            "status": {
                "camera": "gfa0",
                "model": "MicroLine ML4240",
                "serial": "ML0112718",
                "fwrev": 0,
                "hwrev": 0,
                "hbin": 1,
                "vbin": 1,
                "visible_area": [
                    0,
                    0,
                    2048,
                    2048
                ],
                "image_area": [
                    0,
                    0,
                    2048,
                    2048
                ],
                "temperature_ccd": -25.0,
                "temperature_base": -10.0,
                "exposure_time_left": 0,
                "cooler_power": 60.0
            }
        }
    }
    {
        "header": {
            "command_id": 0,
            "commander_id": "8a278303-19bc-4d3b-ba33-a0fc33fdb267",
            "message_code": ":",
            "sender": "flicamera"
        },
        "data": {}
    }

Note that the replies include an empty message with code ``>`` indicating that the command is running, and ``:`` when the command is done. See the :ref:`message codes <clu:message-codes>` for more details.

It's possible to build a camera actor with the same functionality but a different CLU base actor, for example `~clu.AMQPActor` or `~clu.LegacyActor`. To create a camera actor class from a different base actor ::

    from clu import AMQPActor
    from basecam.actor import BaseCameraActor

    class NewActor(BaseCameraActor, AQMPActor):
        pass

The order of the imports is important, always subclass from `.BaseCameraActor` first, and then from the specific CLU base actor. Then initialise the new actor with the parameters necessary for the CLU base actor user.

Default commands
----------------

The following commands are provided by default for any camera actor. They cover all the default functionality provided by ``basecam``. Some commands such as ``binning`` are only available if the camera system includes the corresponding :ref:`mixin <mixins>`. ``basecam`` will automatically detect if that's the case and add the command.

.. click:: basecam.actor.commands.__doc_parser:__doc_parser
   :prog: basecam
   :show-nested:


Adding new commands
-------------------

To add new commands to the actor command parser import the ``camera_parser`` and define new commands ::

    import asyncio
    import click
    from basecam.actor.commands import camera_parser

    @camera_parser.command()
    @click.option('--now', is_flag=True, help='Reboot without delay')
    async def reboot(command, cameras, now):
        if not now:
            asyncio.sleep(1.0)
        for camera in cameras:
            await camera.reboot()
            command.info(reboot={'camera': camera.name, 'text': 'Reboot started'})
        command.finish()

The new actor command always receives a CLU `~clu.command.Command` as the first argument and a list of connected cameras as the second argument. It's possible to access the actor instance as ``command.actor`` and the camera system as ``command.actor.camera_system``. For more details, refer to CLU's :ref:`parser documentation <clu:parser>`.

Schema
------

``basecam`` defines a data model for the actor replies as a `JSONSchema <https://json-schema.org>`__ file. A summary of the schema is given below. When a command issues a reply, the contents are validated against the schema and an error will be generated if the validation fails. The message is not output in that case.

It's possible to opt out of the schema validation by instantiating the `.CameraActor` (or any other subclass of `.BaseCameraActor`) with ``schema=None``.

When adding new commands, you will need to extend the schema and pass it to the camera actor. To do so, first download the `default schema <https://gitcdn.link/repo/sdss/basecam/main/basecam/actor/schema.json>`__ and extend it. For our reboot example we would need to add the following text

.. code-block:: json

    "reboot": {
        "type": "object",
        "properties": {
        "camera": { "type": "string" },
        "text": { "type" "string" },
        "additionalProperties": false
    }

Then do ::

    actor = CameraActor(camera_system, schema='schema.json', host=..., port=...)

An actor command can also manually opt out of validating a specific message by passing ``validate=False`` ::

    command.info(reboot={'camera': camera.name, 'text': 'Reboot started'}, validate=False)

Default schema
^^^^^^^^^^^^^^

.. jsonschema:: ../basecam/actor/schema.json
