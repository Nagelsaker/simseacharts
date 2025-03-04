from __future__ import annotations
from shapely import geometry as geo
import matplotlib.pyplot as plt
import numpy as np
import simcharts.display as dis


class EventsManager:
    _zoom_scale = 0.9
    _heading_step = 5
    _cartesian_step = 50
    _directions = {"up": 1, "down": -1, "left": -1, "right": 1}
    _resizing = {",": 0.9, ".": 1.1, "[": 0.9, "]": 1.1}

    def __init__(self, display: dis.Display):
        self._display = display
        self._canvas = display.figure.canvas
        self._view_limits = dict(x=None, y=None)
        self._direction_keys = {d: False for d in self._directions}
        self._control_pressed = False
        self._shift_pressed = False
        self._mouse_press = None
        self._connect_canvas_events()
        self._remove_default_keybindings()

    def _connect_canvas_events(self):
        self._canvas.mpl_connect("scroll_event", self._handle_zoom)
        self._canvas.mpl_connect("key_press_event", self._key_press)
        self._canvas.mpl_connect("key_release_event", self._key_release)
        self._canvas.mpl_connect("button_press_event", self._click_press)
        self._canvas.mpl_connect("button_release_event", self._click_release)
        self._canvas.mpl_connect("motion_notify_event", self._mouse_motion)

    def _handle_zoom(self, event):
        if event.button == "down":
            scale_factor = 1 / self._zoom_scale
        elif event.button == "up":
            scale_factor = self._zoom_scale
        else:
            raise NotImplementedError
        x_limit = self._display.axes.get_xlim()
        y_limit = self._display.axes.get_ylim()
        new_width = (x_limit[1] - x_limit[0]) * scale_factor
        new_height = (y_limit[1] - y_limit[0]) * scale_factor
        x_data, y_data = event.xdata, event.ydata
        dx = (x_limit[1] - x_data) / (x_limit[1] - x_limit[0])
        dy = (y_limit[1] - y_data) / (y_limit[1] - y_limit[0])
        self._display.axes.set_xlim([x_data - new_width * (1 - dx), x_data + new_width * dx])
        self._display.axes.set_ylim([y_data - new_height * (1 - dy), y_data + new_height * dy])
        self._display.draw_plot()

    def _key_press(self, event):
        if event.key == "escape":
            self._display.terminate()
        elif event.key == "d":
            self._display.toggle_dark_mode()
        elif event.key == "t":
            self._display.features.show_top_hidden_layer()
        elif event.key == "g":
            self._display.features.show_bottom_hidden_layer()
        elif event.key == "h":
            self._display.features.hide_top_visible_layer()
        elif event.key == "b":
            self._display.features.hide_bottom_visible_layer()
        elif event.key == "u":
            self._display.features.update_vessels()
            self._display.update_plot()
        elif event.key == "v":
            self._display.features.toggle_vessels_visibility()
        elif event.key == "l":
            self._display.features.toggle_topography_visibility()
        elif event.key in ["n", "m"]:
            if (
                self._display.environment.ownship
                and self._display.features.show_ownship
                and self._display.environment.depth is not None
            ):
                self._toggle_depth_filter_values(event.key)
        elif event.key == "o":
            if self._display.environment.ownship:
                self._display.features.toggle_ownship_visibility()
            else:
                self._add_ownship_to_plot_center()
        elif event.key == "z":
            self._display.features.toggle_hazards_visibility()
        elif event.key == "a":
            self._display.features.toggle_arrows_visibility()
        elif event.key == "c":
            self._display.toggle_colorbar()
        elif event.key == "f":
            self._display.toggle_fullscreen()
        elif event.key == "ctrl+s":
            self._display.save_figure("svg", extension="svg")
        elif event.key == "s":
            self._display.save_figure("low_res", 2.0)
        elif event.key == "S":
            self._display.save_figure("high_res", 10.0)
        elif event.key in self._directions:
            if self._display.environment.ownship and self._display.features.show_ownship:
                self._direction_keys[event.key] = True
                self._move_ownship()
        elif event.key in self._resizing:
            if self._display.environment.ownship and self._display.features.show_ownship:
                self._resize_hazards_horizon(event.key)
        elif event.key == "ctrl+enter":
            if self._display.features.polygons['main_set']['exterior_connected']:
                if self._display.features.polygons['main_set']['unconnected_interior_points'] != []:
                    self._display.features.polygons['main_set']['interior_points'].append(self._display.features.polygons['main_set']['unconnected_interior_points'])
                    self._display.features.polygons['main_set']['unconnected_interior_points'] = []
            else:
                self._display.features.polygons['main_set']['exterior_connected'] = True
        elif event.key == "shift":
            self._shift_pressed = True
        elif event.key == "control":
            self._control_pressed = True
        elif event.key[:4] == "alt+":
            key = event.key[4:]
            if key in self._directions:
                self._move_figure_position(key)

    def _key_release(self, event):
        if event.key in self._directions:
            self._direction_keys[event.key] = False
        elif event.key == "shift":
            self._shift_pressed = False
        elif event.key == "control":
            self._control_pressed = False

    def _move_figure_position(self, key):
        matrix = self._display.window_anchors
        j, i = self._display.anchor_index
        if key == "left" or key == "right":
            i = (i + self._directions[key]) % len(matrix[0])
        elif key == "up" or key == "down":
            j = (j - self._directions[key]) % len(matrix)
        self._display.anchor_index = j, i
        self._display.set_figure_position()

    def _add_ownship_to_plot_center(self):
        center = self._display.environment.scope.extent.center
        x, y = center[0] - 1414, center[1] - 1414
        self._display.environment.create_ownship(x, y, 45, 1, 10, 10)
        self._display.environment.filter_hazardous_areas(10)
        self._display.features.toggle_ownship_visibility()

    def _move_ownship(self):
        x, y, psi, *params = self._display.environment.ownship.parameters
        if self._direction_keys["up"]:
            x = x + np.sin(np.deg2rad(psi)) * self._cartesian_step
            y = y + np.cos(np.deg2rad(psi)) * self._cartesian_step
        if self._direction_keys["down"]:
            x = x - np.sin(np.deg2rad(psi)) * self._cartesian_step
            y = y - np.cos(np.deg2rad(psi)) * self._cartesian_step
        if self._direction_keys["left"]:
            psi = psi - self._heading_step
        if self._direction_keys["right"]:
            psi = psi + self._heading_step
        self._display.environment.create_ownship(x, y, psi, *params)
        self._display.features.update_ownship()
        self._display.features.update_hazards()
        self._display.update_plot()

    def _resize_hazards_horizon(self, key):
        *other, lon, lat = self._display.environment.ownship.parameters
        if key == "," or key == ".":
            lon *= self._resizing[key]
        else:
            lat *= self._resizing[key]
        self._display.environment.create_ownship(*other, lon, lat)
        self._display.features.update_ownship()
        self._display.features.update_hazards()
        self._display.update_plot()

    def _toggle_depth_filter_values(self, key):
        d = self._display.environment.depth
        d_index = self._display.environment.scope.depths.index(d)
        delta = 1 if key == "m" else -1
        next_d = d_index + delta
        if 0 <= next_d < len(self._display.environment.scope.depths):
            d = self._display.environment.scope.depths[next_d]
            self._display.environment.depth = d
            self._display.environment.filter_hazardous_areas(d)
            self._display.features.update_hazards()
            self._display.update_plot()

    def _click_press(self, event):
        # TODO: Fix this
        if event.inaxes != self._display.axes:
            return
        if self._shift_pressed or self._control_pressed:
            if event.button in [plt.MouseButton.LEFT, plt.MouseButton.RIGHT]:
                pick = [event.xdata, event.ydata]
                coords = pick if event.button == plt.MouseButton.LEFT else None
                path = 1 if self._shift_pressed else 2
                self._mouse_press = dict(x=pick[0], y=pick[1])

                if self._display.features.polygons['main_set']['exterior_connected']:
                    geometry = self._display.features.polygons['main_set']['geometry']
                    p = geo.Point(pick[0], pick[1])
                    if geometry.contains(p):
                        self._display.features.polygons['main_set']['unconnected_interior_points'].append(pick)
                        print(f"Interior waypoint added: {pick}")
                else:
                    self._display.features.polygons['main_set']['exterior_points'].append(pick)
                    print(f"Exterior waypoint added: {pick}")

                interior = self._display.features.polygons['main_set']['interior_points']
                unconnected_interior = self._display.features.polygons['main_set']['unconnected_interior_points']
                if interior == [] and unconnected_interior == []:
                    interior = None
                elif unconnected_interior != [] and len(unconnected_interior) >= 3:
                    interior.append(unconnected_interior)


                exterior = self._display.features.polygons['main_set']['exterior_points']
                if len(exterior) < 3:
                    exterior = None
                
                if exterior is not None:
                    artist, geometry = self._display.features.add_polygon(
                        exterior,
                        color='blue',
                        interiors=interior,
                        fill=True,
                        linewidth=2,
                        linestyle='solid'
                        )
                    if self._display.features.polygons['main_set']['artist'] is not None:
                        self._display.features.polygons['main_set']['artist'].remove()
                    self._display.features.polygons['main_set']['artist'] = artist
                    self._display.features.polygons['main_set']['geometry'] = geometry

                # self._display.features.update_waypoints(path, pick, coords)


                self._display.update_plot()
        else:
            if event.button == plt.MouseButton.LEFT:
                self._view_limits["x"] = self._display.axes.get_xlim()
                self._view_limits["y"] = self._display.axes.get_ylim()
                self._mouse_press = dict(x=event.xdata, y=event.ydata)

    def _click_release(self, _):
        self._mouse_press = None
        self._display.draw_plot()

    def _mouse_motion(self, event):
        if self._mouse_press is None:
            return
        if event.inaxes != self._display.axes:
            return
        if self._shift_pressed or self._control_pressed:
            new_pos = event.xdata, event.ydata
            old_pos = self._mouse_press["x"], self._mouse_press["y"]
            path = 1 if self._shift_pressed else 2
            self._display.features.update_waypoints(path, old_pos, new_pos)
            self._mouse_press = dict(x=new_pos[0], y=new_pos[1])
            self._display.update_plot()
        else:
            self._view_limits["x"] -= event.xdata - self._mouse_press["x"]
            self._view_limits["y"] -= event.ydata - self._mouse_press["y"]
            self._display.axes.set_xlim(self._view_limits["x"])
            self._display.axes.set_ylim(self._view_limits["y"])
            self._display.draw_plot()

    @staticmethod
    def _remove_default_keybindings():
        dic = plt.rcParams
        # dic['keymap.pan'].remove('p')
        # dic["keymap.zoom"].remove("o")
        # dic["keymap.grid"].remove("g")
        # dic["keymap.save"].remove("s")
        # dic["keymap.save"].remove("ctrl+s")
        # dic["keymap.back"].remove("left")
        # dic["keymap.xscale"].remove("k")
        # dic["keymap.yscale"].remove("l")
        # dic["keymap.forward"].remove("v")
        # dic["keymap.forward"].remove("right")
        # # dic['keymap.all_axes'].remove('a')
        # dic["keymap.fullscreen"].remove("f")
