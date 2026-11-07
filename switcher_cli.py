#!/usr/bin/python3

# Copyright 2024 - 2026, Benjamin Drung and the OpenAtem contributors
# SPDX-License-Identifier: LGPL-3.0-only

"""Send single commands to a Blackmagic ATEM video switcher via network or USB.

This tool lets you quickly send individual switcher commands (like cuts,
transitions, or source changes) without opening a full control application. Simply
choose a command, pass any needed settings, and the script handles connecting to
the hardware, sending the instruction, and closing cleanly once confirmed.

Default configuration values (mixer address, M/E index, keyer index) can be
loaded from a TOML file atem.toml located at the XDG config directory.

Configuration Example (atem.toml):
----------------------------------

.. code-block:: toml

    # IP address of the switcher on the local network, or "usb" for direct USB connection
    mixer = "192.168.2.84"
    # Default 0-indexed M/E (Mix Effect) block
    index = 0
    # Default 0-indexed upstream keyer
    keyer = 0

Usage Examples:
---------------

List all dynamically discovered commands and their parameters:
    $ %(prog)s --list-commands

Send a cut command on M/E 0 using settings from atem.toml:
    $ %(prog)s cut

Trigger an auto transition on M/E 1 over USB:
    $ %(prog)s --mixer usb --index 1 auto

Change the program input on M/E 0 to camera input 1:
    $ %(prog)s program-input source=1

Change the preview input on M/E 0 to camera input 2 using a positional parameter:
    $ %(prog)s preview-input 2

Set the PiP / DVE keyer to the bottom-right corner using a shorthand preset:
    $ %(prog)s pip-position br
"""

import argparse
import dataclasses
import inspect
import logging
import os
import pathlib
import re
import sys
import time
import tomllib
from collections.abc import Iterable
from typing import Self

import pyatem.command
from pyatem.command import Command
from pyatem.logging import setup_logging
from pyatem.protocol import AtemProtocol

XDG_CONFIG_DIR = os.environ.get("XDG_CONFIG_HOME", str(pathlib.Path.home() / ".config"))
DEFAULT_CONFIG = os.path.join(XDG_CONFIG_DIR, "atem.toml")
DEFAULT_INDEX = 0
DEFAULT_KEYER = 0


@dataclasses.dataclass
class Config:
    """Configuration."""

    mixer: str | None
    index: int
    keyer: int

    @classmethod
    def defaults(cls) -> Self:
        """Return configuration with default settings."""
        return cls(None, DEFAULT_INDEX, DEFAULT_KEYER)

    def update(self, mixer: str | None, index: int | None, keyer: int | None) -> None:
        """Update configuration with given settings."""
        if mixer is not None:
            self.mixer = mixer
        if index is not None:
            self.index = index
        if keyer is not None:
            self.keyer = keyer

    def update_from_config_file(self, config_filename: str) -> None:
        """Update configuration with settings from given TOML file."""
        with open(config_filename, "rb") as config_file:
            config = tomllib.load(config_file)
        self.update(config.get("mixer"), config.get("index"), config.get("keyer"))


def get_pyatem_command_class_names() -> Iterable[tuple[str, list[str]]]:
    """Returns a sorted list of all unique class names defined in pyatem.command."""
    for name, obj in inspect.getmembers(pyatem.command, inspect.isclass):
        if not name.endswith("Command") or name == "Command":
            continue
        s = re.sub(r"([a-z0-9])([A-Z])", r"\1-\2", name.removesuffix("Command"))
        kebab_name = s.lower()
        signature = inspect.signature(obj.__init__)
        params = [p for p in signature.parameters.keys() if p != "self"]
        yield kebab_name, params


def get_command_by_name(command_name: str) -> type[Command] | None:
    """Get a command class by the name. The class name has to end with 'Command'."""
    classname = command_name.title().replace("-", "") + "Command"
    return getattr(pyatem.command, classname, None)


def _parse_command_arg_value(value: str) -> bool | int | str:
    """Parse a single string CLI argument into bool, int, or str."""
    if value.lower() in ("true", "false"):
        return bool(value)
    try:
        return int(value)
    except ValueError:
        return value


class Arguments(dict[str, bool | int | str]):
    """Argument parser, store, and validator for command signatures."""

    def __init__(self, signature: inspect.Signature) -> None:
        super().__init__()
        self.signature = signature
        self.param_names = [p for p in signature.parameters.keys() if p != "self"]

    def set_default(self, default_args: dict[str, bool | int | str]) -> None:
        """Set default values for parameters that exist in the signature."""
        for key, value in default_args.items():
            if key in self.param_names:
                self[key] = value

    def set(self, arguments: Iterable[str]) -> None:
        """Parse and assign raw CLI arguments.

        Explicit named arguments (``key=value``) are assigned first. Any
        nameless (positional) arguments are then mapped sequentially to the
        remaining unset parameters in the order they were defined in the
        signature.

        :param arguments: Iterable of CLI arguments (e.g., ``["r", "size=250"]``).
        :raises ValueError: If more positional arguments are supplied than there
            are remaining unset parameters in the signature.
        """
        positional_arguments = []
        for argument in arguments:
            if "=" not in argument:
                positional_arguments.append(argument)
                continue
            key, value = argument.split("=", 1)
            self[key] = _parse_command_arg_value(value)

        for param in self.param_names:
            if not positional_arguments:
                break
            if param in self:
                continue
            self[param] = _parse_command_arg_value(positional_arguments.pop(0))

        if positional_arguments:
            raise ValueError(
                f"Too many positional arguments provided: '{positional_arguments}'"
            )

    def validate(self) -> None:
        """Validate that arguments match the type annotations of a callable."""
        for name, param in self.signature.parameters.items():
            if name not in self:
                continue
            if not isinstance(param.annotation, type):
                continue
            actual_type = type(self[name])
            if actual_type is not param.annotation:
                raise TypeError(
                    f"Argument '{name}' must be {param.annotation.__name__}, "
                    f"got {actual_type.__name__}"
                )


# pylint: disable-next=too-many-instance-attributes
class Switcher:
    """ATEM video mixer."""

    # pylint: disable-next=too-many-arguments,too-many-positional-arguments
    def __init__(
        self,
        ip: str,
        index: int,
        keyer: int,
        command: type[Command],
        arguments: Iterable[str],
    ) -> None:
        if ip == "usb":
            self.switcher = AtemProtocol(usb="auto")
        else:
            self.switcher = AtemProtocol(ip)
        self.index = index
        self.keyer = keyer
        self.command = command
        self.arguments = arguments
        self.done = False
        self.error: Exception | None = None
        self.logger = logging.getLogger("CLI")

    @classmethod
    def from_config_and_command(
        cls, config: Config, command: type[Command], arguments: Iterable[str]
    ) -> Self:
        """Construct Mixer object from Config and Position data classes."""
        assert config.mixer is not None
        return cls(config.mixer, config.index, config.keyer, command, arguments)

    def connect(self) -> None:
        """Connect to mixer."""
        self.switcher.on("connected", self._on_connected)
        self.switcher.connect()

    def _on_connected(self) -> None:
        self.logger.debug("Connected to mixer")
        signature = inspect.signature(self.command.__init__)
        arguments = Arguments(signature)
        arguments.set_default({"index": self.index, "keyer": self.keyer})
        try:
            arguments.set(self.arguments)
            self.logger.debug("Arguments: %s", arguments)
            arguments.validate()
            cmd = self.command(**arguments)
            self.logger.info("Sending command %r", cmd)
            self.switcher.send_commands([cmd])
        except (TypeError, ValueError) as error:
            self.error = error
            self.logger.error("Error: %s", error)
        self.done = True

    def run(self) -> int:
        """Set the position of a DVE keyer."""
        while not self.done:
            self.logger.debug("Calling switcher loop...")
            self.switcher.loop()
        while not self.switcher.is_drained():
            self.logger.debug(
                "Switcher connection not drained. Waiting 0.01 seconds..."
            )
            time.sleep(0.01)
        self.logger.debug("Switcher connection drained.")
        return 1 if self.error else 0


def list_commands() -> None:
    """Print the available commands."""
    print("Available commands:")
    for command, arguments in get_pyatem_command_class_names():
        print(f"{command} ({', '.join(arguments)})")


def parse_args(argv: list[str]) -> tuple[Config, type[Command] | None, list[str]]:
    """Parse command line arguments and return a tuple of Config, command and arguments.

    Return `None` as `Command` for listing all available commands."""
    config = Config.defaults()

    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "-c",
        "--config",
        default=DEFAULT_CONFIG if os.path.exists(DEFAULT_CONFIG) else None,
        help=f"TOML configuration file (default: {DEFAULT_CONFIG})",
    )
    parser.add_argument(
        "-m",
        "--mixer",
        help="IP address of the mixer to connect to"
        " or 'usb' for USB connection (default: %(default)s)",
    )
    parser.add_argument(
        "-i", "--index", type=int, help=f"M/E index (default: {config.index})"
    )
    parser.add_argument(
        "-k", "--keyer", type=int, help=f"Keyer index (default: {config.keyer})"
    )
    parser.add_argument(
        "-l", "--list-commands", action="store_true", help="List available commands"
    )
    parser.add_argument(
        "command",
        nargs="?",
        help="command to send (see --list-commands for all possible comands)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        dest="level",
        action="store_const",
        const=logging.INFO,
        default=None,
        help="Show more log messages",
    )
    parser.add_argument(
        "--debug",
        dest="level",
        action="store_const",
        const=logging.DEBUG,
        help="Display a lot of debugging info",
    )
    parser.add_argument("arguments", nargs="*")
    args = parser.parse_args(argv)

    if args.config is not None:
        config.update_from_config_file(args.config)
    config.update(args.mixer, args.index, args.keyer)

    if args.list_commands:
        return config, None, []

    if args.command is None:
        parser.error("the following argument are required: command")
    if config.mixer is None:
        parser.error("no mixer IP specified")

    command = get_command_by_name(args.command)
    if command is None:
        parser.error(f"Unknown command: {args.command}")

    setup_logging(args.level)
    return config, command, args.arguments


def main(argv: list[str]) -> int:
    """Set the position of a DVE keyer in an ATEM video mixer."""
    config, command, arguments = parse_args(argv)
    if command is None:
        list_commands()
        return 0
    switcher = Switcher.from_config_and_command(config, command, arguments)
    switcher.connect()
    rc = switcher.run()
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))  # pragma: no cover
