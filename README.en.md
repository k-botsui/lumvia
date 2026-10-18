# Lumvia

**A local library for your videos and links.**

[日本語](README.md) · English · [Downloads](https://github.com/k-botsui/lumvia/releases) · [Getting started](#getting-started)

Lumvia is a desktop application for organizing your own videos and links from YouTube, X, Instagram, and TikTok. Save a video segment as a **Cell**, and organize videos and Cells into **Shelves** to find and replay them later.

## Trailer

https://github.com/user-attachments/assets/2d9ee76a-45fb-4727-9154-480e4642e751

[Open trailer (28 seconds, 60 fps)](https://github.com/k-botsui/lumvia/releases/download/v0.2.0-mac-test.7/Lumvia-Trailer-V7.mp4)

[Video and music credits](demo/README.md)

## Download

The application is distributed **exclusively through GitHub Releases**. You do not need a GitHub account or an account on a separate download site.

**The current Mac packages are TEST builds without Developer ID signing or Apple notarization. macOS may block them from opening. A public release that anyone can simply extract and open is not ready yet. The Windows desktop package is also in preparation.**

| Your computer                     | Availability and downloads                                                                                                                                                                                                           |
| --------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Mac — Apple Silicon (Apple chips) | [TEST ZIP](https://github.com/k-botsui/lumvia/releases/download/v0.2.0-mac-test.7/Lumvia-Mac-AppleSilicon-TEST.zip) · [DMG](https://github.com/k-botsui/lumvia/releases/download/v0.2.0-mac-test.7/Lumvia-Mac-AppleSilicon-TEST.dmg) |
| Mac — Intel                       | [TEST ZIP](https://github.com/k-botsui/lumvia/releases/download/v0.2.0-mac-test.7/Lumvia-Mac-Intel-TEST.zip) · [DMG](https://github.com/k-botsui/lumvia/releases/download/v0.2.0-mac-test.7/Lumvia-Mac-Intel-TEST.dmg)               |
| Windows                           | The desktop package is in preparation. The Mac ZIP does not run on Windows.                                                                                                                                                          |

On a Mac, check **Apple menu → About This Mac → Chip / Processor** to choose the correct download. `Source code (zip)` and `Code → Download ZIP` contain source code, not a ready-to-run application. Use the platform-specific files above for the desktop app.

### After extracting the ZIP

1. Find **Lumvia (`Lumvia.app`)** in the extracted contents.
2. For regular use, move it to Applications before opening it. If you chose the DMG, drag Lumvia into Applications.
3. If you need help, check this page and the release notes.

**Included guidance:** Mac TEST 7 ZIPs use a folder labeled with the OS and CPU, with **`00_はじめに_READ_ME_FIRST.html`** and a plain-text copy containing Japanese and English startup instructions. Source-code ZIPs include [`00_START_HERE.html`](00_START_HERE.html) and a plain-text copy.

The Mac package includes Python, Node.js, the database, and FFmpeg. Users do not need to install development tools or enter commands or a server URL. If macOS blocks the current TEST build, keep its security settings enabled and check the [release notes](https://github.com/k-botsui/lumvia/releases/tag/v0.2.0-mac-test.7).

### Verification scope

Bundled services and basic workflows have been tested for both Mac architectures. Local execution of the Intel package was tested under Rosetta. macOS 12 is the build target, not a guarantee of compatibility with every later OS release. Normal first launch after downloading on a clean Mac, and Windows installation and execution, remain unverified. See the [Mac distribution notes](docs/development/MAC_APP.md) for details in Japanese.

## Features

- **Save videos and links** in a single local library.
- **Create Cells** to save, edit, replay, and export segments up to five minutes long as MP4.
- **Organize with Shelves**, covers, colors, tags, notes, and favorites.
- **Share link lists** as a reviewed TXT file and import them into another Lumvia library.
- **Check saved links in bulk** while online. Select links confirmed as broken and review their associated Cells and Shelf memberships before deleting them together.

Connection errors and login restrictions are not treated as deletable broken links. While offline, link checking and deletion through this check are unavailable. Temporary previews of external videos depend on the provider, available formats, and bundled codec support.

## Getting started

1. Choose Add to select your own video or paste a shared link.
2. Open a video and choose Create Cell to select a segment.
3. Add videos and Cells to a Shelf, then find them by title, tags, or notes.
4. To share a link list, review it in Share links. The recipient uses Import links to review and add it.

The current interface uses Japanese labels. Sharing details are documented in [LINK_SHARING.md](docs/development/LINK_SHARING.md).

## Data and privacy

Videos you add, Cells, and Shelves are stored on your computer. The packaged Mac app stores its data in `~/Library/Application Support/Lumvia Desktop/`. Replacing the application does not delete this folder. For a complete backup, quit Lumvia and preserve the entire data folder. A link-list TXT file is not a complete backup of uploaded videos.

External players, metadata, temporary previews, and link checking require connections to the relevant providers or connectivity endpoints. Saving a link alone does not permanently download the video. Review optional images, notes, and other content before sharing a link list. Uploaded video files and authentication credentials are not included in link-list exports.

## License

Lumvia is free for personal, private, noncommercial use under the [Lumvia Personal Use License](LICENSE). It is **not open-source software**. You may download, install, configure, build, and run an unmodified copy on devices you own or control, and make private backups.

Modifying or redistributing the program, commercial or organizational use, and providing it as a service require separate permission from the copyright holders. Your own videos, photos, notes, and outputs remain subject to your own and any applicable third-party rights. Third-party software and media keep their own licenses; see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## Development and technical documentation

[Developer setup (English)](docs/development/SETUP_EN.md) · [日本語の開発手順](docs/development/SETUP_JA.md) · [Architecture](docs/architecture/OVERVIEW.md) · [API](docs/api/README.md) · [Security](SECURITY.md) · [Contributing and permissions](CONTRIBUTING.md)

## Contact

Use [GitHub Issues](https://github.com/k-botsui/lumvia/issues). Issue text, including submissions made through the app's contact form, is public. Do not include private videos, credentials, or logs containing secrets.
