[app]
title = Arrow Lanes
package.name = arrowlanes
package.domain = org.example
source.dir = .
source.include_exts = py,png,jpg,kv,json
version = 0.1
requirements = python3,kivy
orientation = portrait
fullscreen = 0

[buildozer]
log_level = 2
warn_on_root = 1

# Android
android.archs = arm64-v8a
android.permissions =
android.api = 34
android.minapi = 24
