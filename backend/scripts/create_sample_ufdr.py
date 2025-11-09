"""Utility to build a synthetic UFDR archive for local testing.

Run:
    python backend/scripts/create_sample_ufdr.py [output_path]

A file like `storage/sample_data/sample.ufdr` will be created by default.
"""

from __future__ import annotations

import argparse
import base64
import plistlib
import shutil
import sqlite3
import tempfile
import zipfile
from pathlib import Path

from xml.etree import ElementTree as ET


DEFAULT_OUTPUT = Path("storage/sample_data/sample.ufdr1")


def create_message_db(path: Path) -> None:
    """Creates a database with a richer set of messages."""
    connection = sqlite3.connect(path)
    cursor = connection.cursor()
    cursor.execute(
        """
        CREATE TABLE message (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            text TEXT,
            timestamp TEXT,
            sender TEXT,
            receiver TEXT,
            direction TEXT
        )
        """
    )
    messages = [
        # Conversation 1: John and Jane
        (
            "Meeting at 5pm near the blue car.",
            "2024-10-11T16:45:00+00:00",
            "+15551230001",  # John
            "+15551230002",  # Jane
            "outgoing",
        ),
        (
            "Remember to bring the documents.",
            "2024-10-11T16:50:00+00:00",
            "+15551230002",  # Jane
            "+15551230001",  # John
            "incoming",
        ),
        (
            "Will do. See you then.",
            "2024-10-11T16:51:00+00:00",
            "+15551230001",  # John
            "+15551230002",  # Jane
            "outgoing",
        ),
        # Conversation 2: John and Officer Lee
        (
            "Photo of the red car attached.",
            "2024-10-11T17:05:00+00:00",
            "+15551230001",  # John
            "+15551230003",  # Officer Lee
            "outgoing",
        ),
        (
            "Received. Looks suspicious. Can you send location?",
            "2024-10-11T17:06:00+00:00",
            "+15551230003",  # Officer Lee
            "+15551230001",  # John
            "incoming",
        ),
        # Conversation 3: Jane and Alex (New Person)
        (
            "Hey, did you get the package?",
            "2024-10-12T09:15:00+00:00",
            "+15551230002",  # Jane
            "+15551230004",  # Alex North
            "outgoing",
        ),
        (
            "Not yet, still waiting.",
            "2024-10-12T09:20:00+00:00",
            "+15551230004",  # Alex North
            "+15551230002",  # Jane
            "incoming",
        ),
        (
            "This is getting risky. Let's talk on a different app.",
            "2024-10-12T09:21:00+00:00",
            "+15551230002",  # Jane
            "+15551230004",  # Alex North
            "outgoing",
        ),
        # Noise
        (
            "What's for dinner?",
            "2024-10-12T18:30:00+00:00",
            "+15551230001",  # John
            "+15551230002",  # Jane
            "outgoing",
        ),
    ]
    cursor.executemany(
        "INSERT INTO message (text, timestamp, sender, receiver, direction) VALUES (?, ?, ?, ?, ?)",
        messages,
    )
    connection.commit()
    connection.close()


def create_contacts_db(path: Path) -> None:
    """Creates a contacts database with more entries."""
    connection = sqlite3.connect(path)
    cursor = connection.cursor()
    cursor.execute(
        """
        CREATE TABLE contacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            first TEXT,
            last TEXT,
            phone TEXT,
            email TEXT
        )
        """
    )
    contacts = [
        ("John", "Doe", "+15551230001", "john.doe@example.com"),
        ("Jane", "Smith", "+15551230002", "jane.smith@example.com"),
        ("Officer", "Lee", "+15551230003", "officer.lee@example.com"),
        ("Alex", "North", "+15551230004", "a.north@web.com"),
        ("Dr. Emily", "White", "+15551230005", "ewhite@hospital.org"), # Unrelated
    ]
    cursor.executemany(
        "INSERT INTO contacts (first, last, phone, email) VALUES (?, ?, ?, ?)",
        contacts,
    )
    connection.commit()
    connection.close()


def create_call_log_db(path: Path) -> None:
    """Creates a new call log database, perfect for the knowledge graph."""
    connection = sqlite3.connect(path)
    cursor = connection.cursor()
    cursor.execute(
        """
        CREATE TABLE calllog (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            caller TEXT,
            receiver TEXT,
            duration_sec INTEGER,
            direction TEXT
        )
        """
    )
    calls = [
        # John calls Jane
        (
            "2024-10-11T16:40:00+00:00",
            "+15551230001",
            "+15551230002",
            120,
            "outgoing",
        ),
        # Officer Lee calls John
        (
            "2024-10-11T17:10:00+00:00",
            "+15551230003",
            "+15551230001",
            35,
            "incoming",
        ),
        # Jane calls Alex
        (
            "2024-10-12T09:10:00+00:00",
            "+15551230002",
            "+15551230004",
            45,
            "outgoing",
        ),
        # Alex calls Jane (missed call)
        (
            "2024-10-12T09:18:00+00:00",
            "+15551230004",
            "+15551230002",
            0,
            "incoming",
        ),
    ]
    cursor.executemany(
        "INSERT INTO calllog (timestamp, caller, receiver, duration_sec, direction) VALUES (?, ?, ?, ?, ?)",
        calls,
    )
    connection.commit()
    connection.close()


def create_report_xml(path: Path) -> None:
    """Creates the main report XML."""
    root = ET.Element("report")
    meta = ET.SubElement(root, "metadata")
    ET.SubElement(meta, "caseName").text = "Sample UFDR"
    ET.SubElement(meta, "generatedOn").text = "2024-10-13T10:00:00Z"
    ET.SubElement(meta, "analyst").text = "Gemini"

    evidence = ET.SubElement(root, "evidence")
    device = ET.SubElement(evidence, "device")
    ET.SubElement(device, "name").text = "Pixel 7"
    ET.SubElement(device, "owner").text = "John Doe"
    ET.SubElement(device, "model").text = "G10"
    ET.SubElement(device, "serial").text = "SAMPLE-SERIAL-12345"

    tree = ET.ElementTree(root)
    tree.write(path, encoding="utf-8", xml_declaration=True)


def create_system_plist(path: Path) -> None:
    """Creates a more detailed system info plist."""
    data = {
        "DeviceName": "Pixel 7",
        "OSVersion": "Android 14",
        "BuildVersion": "AP1A.241005.006",
        "SerialNumber": "SAMPLE-SERIAL-12345",
        "Timezone": "America/New_York",
        "Locale": "en_US",
        "InstalledApps": [
            {"name": "Messages", "version": "2024.09"},
            {"name": "Camera", "version": "1.4.2"},
            {"name": "Chrome", "version": "118.0.5993.111"},
            {"name": "Signal", "version": "6.30.5"},
        ],
    }
    with path.open("wb") as handle:
        plistlib.dump(data, handle)


def create_sample_image_red(path: Path) -> None:
    """Creates a 1x1 red PNG."""
    # Tiny 1x1 red PNG encoded in base64.
    png_bytes = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGMAAQAABQABDQottAAAAABJRU5ErkJggg=="
    )
    path.write_bytes(png_bytes)


def create_sample_image_blue(path: Path) -> None:
    """Creates a 1x1 blue PNG."""
    # Tiny 1x1 blue PNG encoded in base64.
    png_bytes = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGMAAvoAAXsB2cpmAAAAAElFTkSuQmCC"
    )
    path.write_bytes(png_bytes)


def build_archive(
    output_path: Path,
    red_image: Path | None = None,
    blue_image: Path | None = None,
) -> Path:
    """Builds the final .ufdr (zip) archive."""
    if red_image and not red_image.is_file():
        raise FileNotFoundError(f"Red image not found: {red_image}")
    if blue_image and not blue_image.is_file():
        raise FileNotFoundError(f"Blue image not found: {blue_image}")

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_root = Path(temp_dir)

        # Define directory structure
        report_path = temp_root / "report.xml"
        databases_dir = temp_root / "databases"
        contacts_dir = temp_root / "contacts"
        system_dir = temp_root / "system"
        media_dir = temp_root / "media/images"

        # Create directories
        databases_dir.mkdir(parents=True, exist_ok=True)
        contacts_dir.mkdir(parents=True, exist_ok=True)
        system_dir.mkdir(parents=True, exist_ok=True)
        media_dir.mkdir(parents=True, exist_ok=True)

        # Create data files
        create_report_xml(report_path)
        create_message_db(databases_dir / "messages.sqlite")
        create_call_log_db(databases_dir / "calllogs.sqlite") # New call log DB
        create_contacts_db(contacts_dir / "addressbook.sqlite")
        create_system_plist(system_dir / "device_info.plist")
        
        # Create image files
        if red_image:
            suffix = red_image.suffix or ".png"
            shutil.copy2(red_image, media_dir / f"red-car{suffix}")
        else:
            create_sample_image_red(media_dir / "red-car.png")

        if blue_image:
            suffix = blue_image.suffix or ".png"
            shutil.copy2(blue_image, media_dir / f"blue-car{suffix}")
        else:
            create_sample_image_blue(media_dir / "blue-car.png") # New image

        # Zip the contents
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for file_path in temp_root.rglob("*"):
                if file_path.is_file():
                    archive.write(file_path, file_path.relative_to(temp_root))

    return output_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a synthetic UFDR archive for testing")
    parser.add_argument(
        "output",
        nargs="?",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Destination UFDR archive (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--red-image",
        type=Path,
        help="Path to a custom image to use instead of the synthetic red car",
    )
    parser.add_argument(
        "--blue-image",
        type=Path,
        help="Path to a custom image to use instead of the synthetic blue car",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    archive_path = build_archive(args.output, args.red_image, args.blue_image)
    print(f"Sample UFDR created at: {archive_path.resolve()}")


if __name__ == "__main__":
    main()