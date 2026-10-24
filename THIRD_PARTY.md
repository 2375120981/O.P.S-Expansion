# Tooling provenance

The minimal Stingray archive writer and offline Lua runner were selectively adapted from the retained HD2Runtime authoring SDK. The archive writer documents its Bingus-tooling origin. Only these small offline helpers are included; HD2Runtime is not a runtime or build dependency.

Bingus Shared Loader remains a separate dependency. No game binaries, memory dumps, loader distribution or complete third-party SDK is included. The offline runner loads the developer's installed lua51.dll without redistributing it.
