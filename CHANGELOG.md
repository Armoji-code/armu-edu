# Changelog

All notable changes to Armu are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [0.7.0] - 2026-05-23

### Added
- **Real-time personal messages** — incoming messages appear instantly via SocketIO; no refresh needed
- **Read receipts** — messages are marked read when you open a conversation; unread dot disappears immediately
- **Group chat** — study groups now have a Members | Chat tab switcher with full real-time group messaging
- **File attachments** — paperclip button in the message compose area; images render inline, other files as a download card; 10 MB limit; supported types: jpg/png/gif/webp, pdf, doc/docx, xls/xlsx, ppt/pptx, zip, txt
- **Message actions** — hover over any bubble to reveal: edit and delete (own messages), reply with quote, forward, emoji reactions (👍❤️😂😮😢😡), report to admins
- **Reply threading** — reply banner in the compose area shows who you're replying to; quoted block appears above the replied-to bubble
- **Message reporting** — creates a flagged-message entry (severity 0.6) visible in the admin Flagged panel
- **Admin Personal nav section** — admins now have Messages, Whiteboard, Meeting, and My Settings in their sidebar

### Fixed
- Deleted messages no longer reappear as `[Message deleted]` after a page refresh (soft-delete rows excluded from API response)
- Message action bar caused the bubble to shift sideways on hover — now slides in below the bubble with a smooth max-height transition
- groups.html partial was missing all modal/panel HTML (only existed in the standalone page); rewritten with create modal and detail panel
- Script load order: `socket.io.min.js` now loads before `notif.js`

---

## [0.6.0] - 2026-05-22

### Added
- **AI message moderation** — silent background scan on all messages using a local `llama3.2:3b` model; flags messages with severity ≥ 0.5 without alerting the sender
- **Flagged Messages panel** — dedicated admin tab (Admin → Flagged) with severity bar, AI reason, sender → recipient, Dismiss / Action buttons, and Pending / Dismissed / Actioned filter tabs
- **Sidebar flag badge** — Flagged nav item shows a live count of pending flags, refreshed on every navigation
- **Infinite whiteboard** — pan/zoom canvas (scroll to zoom, hand tool to pan, H/Space shortcuts); zoom capped at 4×; `0` resets view
- **Whiteboard selection tool** — rubber-band select strokes and images; move, resize, or delete selection; images individually resizable
- **Whiteboard export area** — drag to define an export rectangle; exports only that region as PNG
- **Whiteboard palette** — black and white swatches added
- **Custom navigation** — admins can rearrange, rename, and reorder the sidebar nav per role (Admin → Navigation)
- **New conversation picker** — `+` button in messages opens a user search modal to start a conversation with anyone in the school
- **Meeting chat** — in-call sidebar has People | Chat tabs; Chat tab sends and receives messages in real time (SocketIO `meeting:chat` event, participants only)
- **Meeting quick-links** — Chat and Whiteboard buttons in the meeting controls panel

---

## [0.5.0] - 2026-05-18

### Added
- **Web terminal** — full PTY shell session in the browser (Admin → Terminal); xterm.js frontend with color theme and resize
- **In-app updates** — Admin → Settings → Software Update checks GitHub for new versions; applies with one click (git pull + pip install + db migrate + auto-restart)
- **Logo size slider** — adjustable logo height (16–94 px) in Admin → Settings → Customize
- **Production deployment** — `deploy.sh` sets up nginx, Let's Encrypt HTTPS, and a systemd service; supports Ubuntu/Debian and Arch/CachyOS

### Fixed
- `setup.sh` now always creates an admin account; demo accounts are opt-in (default N)
- `seed.py` was missing `admin@test.com` despite claiming to create it
- Settings save bar position (fixed layout, no gap, scrolling intact)

---

## [0.4.0] - 2026-05-15

### Added
- **School branding** — admins can upload a custom school logo shown in the sidebar; "Use Default" button resets it
- **Accent colour theming** — primary, secondary, and tertiary accent colours configurable in Admin → Settings with live preview
- **Full theme propagation** — replaced all hardcoded colour values with CSS variables so custom colours apply everywhere instantly

### Fixed
- Settings save bar is now `position:fixed` at the viewport bottom with no gap and no layout shift

---

## [0.3.1] - 2026-05-12

### Fixed
- Server now binds to `0.0.0.0`; other devices on the same LAN can reach it at the host's local IP
- `/admin` and `/teacher` root paths now load the correct dashboard
- Profile page sign-out button added for all roles
- Admin users page: missing modal caused infinite loading; fixed
- Assignment modal: "New Assignment" button did nothing (modal HTML was missing); fixed
- Removed a rogue `max-width: 680px` on `.content` that squished every page
- Page revisit no longer gets stuck loading; router rewrites `const`/`let` → `var` so scripts are safely re-runnable
- onclick handlers broken by earlier IIFE-wrapping approach; functions now properly in global scope
- Profile sidebar corruption when navigating as admin or librarian

---

## [0.3.0] - 2026-05-10

### Added
- **In-call whiteboard** — whiteboard icon in call topbar opens collaborative whiteboard in a left-side tab panel
- **Participants toggle** — dedicated button in call topbar hides/shows the participants sidebar

### Fixed
- Assignment creation modal was missing from the HTML; restored with all fields
- Page layout: settings-specific CSS was cascading globally and squishing every page

---

## [0.2.0] - 2026-05-05

### Added
- Real-time collaborative whiteboard (canvas, shapes, text tool, eraser)
- WebRTC video meetings (camera, mic, screen share, multi-peer)
- Direct messaging between users
- Group study rooms with shared AI chat sessions
- Teacher assignment management and grade sheet
- Admin performance monitoring dashboard
- Notification system with real-time SocketIO delivery

---

## [0.1.0] - 2026-04-28

### Added
- Initial release: student dashboard, AI tutor, homework/tests, schedule, grades, calendar, leaderboard, library, activities, conduct log
- Multi-role auth: student / teacher / admin / librarian
- Multi-provider AI: Ollama / OpenAI / Anthropic
- APScheduler deadline reminders and weekly AI digest
