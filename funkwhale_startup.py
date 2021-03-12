from config import plugins


PLUGIN = plugins.get_plugin_config(
    name="predatumscrobbler",
    label="Predatum scrobbler",
    description="A Flunkwhale plugin that allows you to submit your listens to predatum.",
    version="0.1",
    user=True,
    conf=[
        {"name": "username", "type": "text", "label": "Predatum username"},
        {"name": "password", "type": "password", "label": "Predatum password"},
    ],
)
