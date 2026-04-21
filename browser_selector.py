#!/usr/bin/env python3
"""
Browser Selector for NixOS
Equivalent to browser_selector.ahk + picker.html

Register as default browser, and it will:
  - Parse the URL
  - Auto-launch a browser if a rule matches
  - Otherwise show a picker GUI where you can optionally save a new rule
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import shutil
import tkinter as tk
from tkinter import ttk
from pathlib import Path
from typing import Any

# ── Settings discovery ────────────────────────────────────────────────────────

SCRIPT_DIR = Path(__file__).resolve().parent
_IN_NIX_STORE = str(SCRIPT_DIR).startswith("/nix/store")

# When running from the Nix store the script path is read-only,
# so only consider the XDG path.  Outside the store (dev / Windows)
# prefer a settings.json next to the script so the project stays
# self-contained.
CONFIG_PATHS: list[Path] = (
  [Path.home() / ".config" / "browser-selector" / "settings.json"]
  if _IN_NIX_STORE
  else [
    SCRIPT_DIR / "settings.json",
    Path.home() / ".config" / "browser-selector" / "settings.json",
  ]
)

DEFAULT_SETTINGS: dict[str, Any] = {
  "settings": {
    "closeOnFocusLoss": True,
    "defaultBrowser": "",
    "closeOnEscPressed": True,
    "hideEmptyProperties": True,
    "alwaysOnTop": True,
  },
  "programs": {
    "__default__": {
      "path": "__default__",
      "args": ["$url"],
    },
    "firefox": {
      "path": "firefox",
      "args": ["$url"],
    },
    "chromium": {
      "path": "chromium",
      "args": ["$url"],
    },
  },
  "rules": [],
}


def find_settings_file() -> Path:
  for p in CONFIG_PATHS:
    if p.exists():
      return p
  # Bootstrap default config — always write to the last (writable) path
  path = CONFIG_PATHS[-1]
  path.parent.mkdir(parents=True, exist_ok=True)
  save_settings(path, DEFAULT_SETTINGS)
  print(f"Created default settings at {path}", file=sys.stderr)
  return path


def load_settings(path: Path) -> dict[str, Any]:
  try:
    with open(path) as f:
      return json.load(f)
  except Exception as e:
    print(f"Failed to load settings: {e}", file=sys.stderr)
    return dict(DEFAULT_SETTINGS)


def save_settings(path: Path, settings: dict):
  with open(path, "w") as f:
    json.dump(settings, f, indent=2)


# ── URL parser ────────────────────────────────────────────────────────────────


def parse_url(url: str) -> dict:
  """
  Break a URL/path into the same fields as the AHK version:
  url, protocol, fulldomain, tld, subdomain, maindomainonly,
  maindomain, path, perams, port, hash, fileName, drive,
  fileNameAndExt, fileExt
  """
  parsed: dict = {
    "url": url,
    "protocol": "",
    "fulldomain": "",
    "tld": "",
    "subdomain": "",
    "maindomainonly": "",
    "maindomain": "",
    "path": "",
    "perams": "",
    "port": "",
    "hash": "",
    "fileName": "",
    "drive": "",
    "fileNameAndExt": "",
    "fileExt": "",
  }

  # Windows-style drive letter path
  if re.match(r"^[a-zA-Z]:\\", url) or re.match(r"^[a-zA-Z]:/", url):
    m = re.match(r"^([a-zA-Z])[:\\/]", url)
    if m:
      parsed["drive"] = m.group(1)
    parsed["protocol"] = "file"
    m = re.match(r"^.*[/\\]", url)
    if m:
      parsed["path"] = m.group(0)
    m = re.search(r"([^/\\]+)\.([^.]+)$", url)
    if m:
      parsed["fileName"] = m.group(1)
      parsed["fileExt"] = m.group(2)
      parsed["fileNameAndExt"] = m.group(1) + "." + m.group(2)
    return parsed

  # Unix file path
  if url.startswith("file://"):
    parsed["protocol"] = "file"
    rest = url[7:]
    parsed["path"] = str(Path(rest).parent) + "/"
    m = re.search(r"([^/]+)\.([^.]+)$", rest)
    if m:
      parsed["fileName"] = m.group(1)
      parsed["fileExt"] = m.group(2)
      parsed["fileNameAndExt"] = m.group(1) + "." + m.group(2)
    return parsed

  # http / https
  m = re.match(r"^(https?)://", url)
  if m:
    parsed["protocol"] = m.group(1)
    rest = url[m.end() :]

    # IP address
    ip_m = re.match(
      r"((?:(?:[1-2][0-9]{2}|[0-9]|[1-9][0-9])\.){3}"
      r"(?:[1-2][0-9]{2}|[0-9]|[1-9][0-9]))\b",
      rest,
    )
    if ip_m:
      parsed["fulldomain"] = ip_m.group(1)
      rest = rest[ip_m.end() :]
    else:
      dom_m = re.match(r"([^:/?#]+)", rest)
      if dom_m:
        fd = dom_m.group(1)
        parsed["fulldomain"] = fd
        rest = rest[dom_m.end() :]
        tld_m = re.search(r"\.(\w+)$", fd)
        if tld_m:
          parsed["tld"] = tld_m.group(1)
        sub_m = re.match(r"^(.+)(?:\.\w+){2}$", fd)
        if sub_m:
          parsed["subdomain"] = sub_m.group(1)
        main_m = re.search(r"(\w+)\.(\w+)$", fd)
        if main_m:
          parsed["maindomainonly"] = main_m.group(1)
          parsed["maindomain"] = main_m.group(1) + "." + main_m.group(2)

    # Port
    port_m = re.match(r":(\d{1,5})\b", rest)
    if port_m and int(port_m.group(1)) <= 65535:
      parsed["port"] = port_m.group(1)
      rest = rest[port_m.end() :]

    # Path
    path_m = re.match(r"(/[^?#]*)", rest)
    if path_m:
      parsed["path"] = path_m.group(1)
      rest = rest[path_m.end() :]

    # Query string
    params_m = re.match(r"(\?[^#]+)", rest)
    if params_m:
      parsed["perams"] = params_m.group(1)
      rest = rest[params_m.end() :]

    # Hash / fragment
    hash_m = re.match(r"(#.*)", rest)
    if hash_m:
      parsed["hash"] = hash_m.group(1)

    return parsed

  # Any other protocol  (mailto:, steam:, spotify:, …)
  m = re.match(r"^(\w+):", url)
  if m:
    parsed["protocol"] = m.group(1)

  return parsed


# ── Rule matching ─────────────────────────────────────────────────────────────


def do_they_match(thing1: str, matchtype: str, thing2: str) -> bool:
  try:
    if matchtype == "is":
      fmt = lambda s: s.replace("\\", "/").strip("/ ")
      return fmt(thing1) == fmt(thing2)
    elif matchtype == "isexact":
      return thing1 == thing2
    elif matchtype == "startswith":
      return thing1.startswith(thing2)
    elif matchtype == "endswith":
      return thing1.endswith(thing2)
    elif matchtype == "matchesregex":
      return bool(re.search(thing2, thing1))
    elif matchtype == "includes":
      return thing2 in thing1
  except Exception:
    pass
  return False


# ── Program launcher ──────────────────────────────────────────────────────────


def resolve_path(path: str) -> str | None:
  """Return absolute path if found, or None."""
  if path == "__default__":
    return "__default__"
  if os.path.isabs(path) and os.path.isfile(path):
    return path
  found = shutil.which(path)
  return found # None if not found


def run_program(prog_name: str, settings: dict, match: dict):
  """Launch prog_name, substituting $vars from match into args."""
  if not prog_name:
    return

  programs = settings.get("programs", {})

  if prog_name == "__default__":
    subprocess.Popen(["xdg-open", match["url"]])
    sys.exit(0)

  if prog_name not in programs:
    print(f"Program '{prog_name}' not in settings", file=sys.stderr)
    return

  program = programs[prog_name]
  paths = program.get("path", "__default__")
  if isinstance(paths, str):
    paths = [paths]

  for raw_path in paths:
    exe = resolve_path(raw_path)
    if not exe:
      print(f"Not found: {raw_path}", file=sys.stderr)
      continue

    if exe == "__default__":
      subprocess.Popen(["xdg-open", match["url"]])
      sys.exit(0)

    args_tmpl = program.get("args", ["$url"])
    args = []
    for arg in args_tmpl:

      def sub(m, _match=match):
        key = m.group(1)
        return str(_match.get(key, m.group(0)))

      args.append(re.sub(r"\$(\w+)", sub, arg))

    cmd = [exe] + args
    print("Launching:", cmd, file=sys.stderr)
    subprocess.Popen(cmd)
    sys.exit(0)

  print(f"No executable found for '{prog_name}'", file=sys.stderr)


# ── Picker GUI ────────────────────────────────────────────────────────────────

BG = "#777777"
BG_ROW_A = "#999999"
BG_ROW_B = "#777777"
BG_BTN = "#4b4b4b"
FG_BTN = "#d6d6d6"
BG_MATCH = "#06b300"
BG_NOMATCH = "#b30000"

MATCH_TYPES = ["is", "matchesregex", "isexact", "startswith", "endswith", "includes"]


def show_picker(url: str, match: dict, settings: dict, settings_path: Path):
  user_settings = settings.get("settings", {})
  hide_empty = user_settings.get("hideEmptyProperties", True)
  always_on_top = user_settings.get("alwaysOnTop", True)
  close_on_esc = user_settings.get("closeOnEscPressed", True)
  close_on_blur = user_settings.get("closeOnFocusLoss", True)

  root = tk.Tk()
  root.title("Browser Selector")
  root.configure(bg=BG)
  root.resizable(True, True)
  if always_on_top:
    root.attributes("-topmost", True)

  # Grid: row 0 = URL bar (fixed), row 1 = canvas (expands), row 2 = buttons (fixed)
  root.grid_rowconfigure(1, weight=1)
  root.grid_columnconfigure(0, weight=1)

  # ── URL bar ───────────────────────────────────────────────────────────────
  url_var = tk.StringVar(value=url)
  url_entry = tk.Entry(
    root, textvariable=url_var, bg="#999999", fg="black", relief="flat", bd=2
  )
  url_entry.grid(row=0, column=0, columnspan=2, sticky="ew", padx=4, pady=(4, 2))

  # ── Scrollable match-options area ─────────────────────────────────────────
  canvas = tk.Canvas(root, bg=BG, highlightthickness=0)
  scroll = tk.Scrollbar(root, orient="vertical", command=canvas.yview)
  canvas.configure(yscrollcommand=scroll.set)
  canvas.grid(row=1, column=0, sticky="nsew", padx=(4, 0))
  scroll.grid(row=1, column=1, sticky="ns")

  inner = tk.Frame(canvas, bg=BG)
  canvas_window = canvas.create_window((0, 0), window=inner, anchor="nw")

  def on_frame_configure(_event=None):
    canvas.configure(scrollregion=canvas.bbox("all"))

  def on_canvas_configure(event):
    canvas.itemconfig(canvas_window, width=event.width)

  inner.bind("<Configure>", on_frame_configure)
  canvas.bind("<Configure>", on_canvas_configure)

  # Mouse-wheel scrolling
  def _on_wheel(event):
    canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

  canvas.bind_all("<MouseWheel>", _on_wheel)
  canvas.bind_all("<Button-4>", lambda e: canvas.yview_scroll(-1, "units"))
  canvas.bind_all("<Button-5>", lambda e: canvas.yview_scroll(1, "units"))

  # Build one row per URL field
  row_vars: dict[str, tuple] = {} # key → (BoolVar, StringVar type, StringVar value)

  for i, (key, val) in enumerate(match.items()):
    val_str = str(val)
    if hide_empty and not val_str:
      continue

    row_bg = BG_ROW_A if i % 2 == 0 else BG_ROW_B
    row = tk.Frame(inner, bg=row_bg)
    row.pack(fill="x", pady=1)

    checked_var = tk.BooleanVar()
    type_var = tk.StringVar(value="is")
    value_var = tk.StringVar(value=val_str)

    tk.Checkbutton(
      row, variable=checked_var, bg=row_bg, activebackground=row_bg
    ).pack(side="left")
    tk.Label(row, text=key, width=16, anchor="w", bg=row_bg, fg="black").pack(
      side="left"
    )

    type_cb = ttk.Combobox(
      row, textvariable=type_var, values=MATCH_TYPES, width=11, state="readonly"
    )
    type_cb.pack(side="left", padx=2)

    val_entry = tk.Entry(
      row, textvariable=value_var, bg=BG_MATCH, fg="black", relief="flat"
    )
    val_entry.pack(side="left", fill="x", expand=True, padx=(0, 4))

    def make_validator(v_var, v_entry, t_var, orig):
      def _validate(*_):
        try:
          matches = do_they_match(orig, t_var.get(), v_var.get())
        except Exception:
          matches = False
        v_entry.configure(bg=BG_MATCH if matches else BG_NOMATCH)

      v_var.trace_add("write", _validate)
      t_var.trace_add("write", _validate)

    make_validator(value_var, val_entry, type_var, val_str)

    row_vars[key] = (checked_var, type_var, value_var)

  # ── Program buttons ───────────────────────────────────────────────────────
  btn_frame = tk.Frame(root, bg=BG)
  btn_frame.grid(row=2, column=0, columnspan=2, sticky="ew", padx=4, pady=4)
  btn_frame.grid_columnconfigure(0, weight=1)

  def make_handler(prog_name: str):
    def _open():
      # Collect checked rules
      rules_to_add = [
        [k, tv.get(), vv.get()]
        for k, (chk, tv, vv) in row_vars.items()
        if chk.get()
      ]
      if rules_to_add:
        new_rule = {"name": prog_name, "matches": rules_to_add}
        settings.setdefault("rules", []).append(new_rule)
        save_settings(settings_path, settings)

      match["url"] = url_var.get()
      root.destroy()
      run_program(prog_name, settings, match)

    return _open

  # "Block" button (no program)
  tk.Button(
    btn_frame,
    text="BLOCK URL",
    bg=BG_BTN,
    fg=FG_BTN,
    relief="raised",
    bd=3,
    command=root.destroy,
  ).pack(fill="x", pady=1)

  programs = settings.get("programs", {})
  for name, data in programs.items():
    if not data.get("visible", True):
      continue
    tk.Button(
      btn_frame,
      text=name,
      bg=BG_BTN,
      fg=FG_BTN,
      relief="raised",
      bd=3,
      command=make_handler(name),
    ).pack(fill="x", pady=1)

  # ── Key / focus bindings ──────────────────────────────────────────────────
  if close_on_esc:
    root.bind("<Escape>", lambda _: root.destroy())

  if close_on_blur:

    def _on_blur(event: "tk.Event[tk.Misc]") -> None:
      # focus_get() raises KeyError when a ttk.Combobox dropdown
      # ('popdown') temporarily steals focus — that's not a real blur.
      try:
        focused = root.focus_get()
      except KeyError:
        return # combobox dropdown opened, ignore
      if focused is None:
        root.destroy()

    root.bind("<FocusOut>", _on_blur)

  root.update_idletasks()
  # Center on screen
  w, h = root.winfo_reqwidth(), root.winfo_reqheight()
  sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
  root.geometry(f"{max(w, 420)}x{max(h, 300)}+{(sw-420)//2}+{(sh-300)//2}")

  root.mainloop()


# ── Entry point ───────────────────────────────────────────────────────────────


def main():
  args = sys.argv[1:]
  force = any(a in ("--force", "-force", "/force") for a in args)
  url_args = [a for a in args if a not in ("--force", "-force", "/force")]
  url = url_args[0] if url_args else "###TESTING###"

  settings_path = find_settings_file()
  settings = load_settings(settings_path)
  user_settings = settings.get("settings", {})

  match = parse_url(url)

  if not force:
    # 1. Default browser shortcut
    default = user_settings.get("defaultBrowser", "")
    if default and default in settings.get("programs", {}):
      run_program(default, settings, match)
      return

    # 2. Walk rules
    for rule in settings.get("rules", []):
      all_match = all(
        do_they_match(str(match.get(k, "")), mt, v)
        for k, mt, v in rule.get("matches", [])
      )
      if all_match:
        name = rule.get("name")
        if not name:
          return # URL blocked
        run_program(name, settings, match)
        return

  # 3. Show picker
  show_picker(url, match, settings, settings_path)


if __name__ == "__main__":
  main()
