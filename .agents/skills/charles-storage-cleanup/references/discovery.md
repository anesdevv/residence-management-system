# Thorough storage discovery

Use this checklist for broad cleanup, rarely used applications, or requests for more opportunities. The locations are discovery leads, not deletion rules. Resolve the current user's configured paths and measure what actually exists; historical sizes and app names are not evidence of present garbage. Read the relevant [macOS procedures](macos.md) before acting.

## Map and cover

Start with filesystem-bounded summaries of the home directory, `/Applications`, `/Library`, `/Users/Shared`, and the current user's Library. Include hidden home directories. Check mounts before traversing `/private/var` or developer device directories. Expand large branches with targeted, time-bounded probes rather than repeating a recursive scan of the entire machine.

Record a compact coverage table: family, roots checked, completion/errors, exclusions, and follow-up. Permission failures and timeouts mean uninspected, not empty. Pair large-directory measurements with a largest-files view: many separate 200 MB–2 GB stores can add up even when no single file dominates. After large removals, inspect these smaller contributors.

For every finding, record exact paths/subsets, allocated size, data type, purpose, evidence of recent use, reconstruction/dependency requirements, and deletion method. Rank by likely recovery and confidence. Keep unique data and optional uninstalls visible as decisions without calling them junk.

## Applications, bundles, and remnants

| Family | Where and what to inspect | Interpretation |
| --- | --- | --- |
| Installed apps | `/Applications`, `~/Applications`, nested Utilities/vendor folders; a bounded native application inventory can help discover other locations | Record bundle ID, version/build, allocated size, running processes, and Spotlight last-use metadata. Missing last use is unknown; install/update dates are not launch dates. |
| Bundle contents | `Contents/Frameworks`, `Resources`, helpers, embedded runtimes, SDKs, architecture slices, bundled models and media | Explain why the bundle is large. Signed components such as Xcode's Icon Composer are not independent junk; use a supported component manager or uninstall the whole selected app. |
| Editor extensions | `~/.cursor/extensions`, `~/.vscode/extensions`, IDE plugin directories and their native extension lists | Identify installed versus obsolete versions, remote/server copies, dependencies, and active extensions. A large pool can be useful; preserve chats, settings and workspace state unless separately selected. |
| Product remnants | Both Library trees: Application Support, Caches, Preferences, Containers, Group Containers, LaunchAgents/Daemons, PrivilegedHelperTools, PreferencePanes and StartupItems; also `/Users/Shared` | Map exact bundle IDs and service executables to the selected product. Check retired helpers' OS cache directories too. A familiar vendor name alone does not prove exclusive ownership. |
| Optional creative assets | GarageBand/Logic instruments, lessons and factory samples; `/Library/Application Support/{GarageBand,Logic}`, `/Library/Audio/Apple Loops`; Unity/editor download and package stores | Distinguish downloadable factory content from custom samples, projects, presets and licensing. Shared sound libraries may serve other apps even when the original app is absent. |
| Supporting tools and game payloads | DaVinci prerequisites/control-panel utilities, MathWorks ServiceHost, Logitech companion/plugin services, Riot's shared client, Minecraft assets, other launcher-managed downloads | Measure installed payload separately from caches. Preserve project databases/LUTs, licensing, input/camera components for retained products, game worlds, saves, mods and custom content. |
| Updater packages | `*-updater/pending`, Electron updater caches, Dropbox `DropboxUpdater/crx_cache`, installer ZIP/DMG/PKG archives | Compare archive metadata with installed version/build or a retained equivalent. List/read small metadata from an archive rather than extracting an entire package. Keep in-progress downloads and live updater inputs. |
| App/browser caches | `~/Library/Caches/com.spotify.client/{Browser/Cache,Data,component_crx_cache}`, browser HTTP/GPU/code caches, `~/Library/Application Support/Claude/{Cache,Code Cache}` and other Electron cache stores | Separate cache from IndexedDB, local storage, offline user content, accounts and conversation databases. A browser profile or a directory named Data is not inherently disposable. |
| Archived profiles and retired app data | Dated/archived browser profiles, old app-version folders and support data for uninstalled apps, including locations outside the main profile tree | Inspect provenance and allocated size. Distinguish a redundant archive from the only copy of history, credentials, sessions or local documents; profile deletion needs its own scope. |

For unused-app reviews, use current processes and available Spotlight metadata, for example `mdls -name kMDItemLastUsedDate <app>`. Report the date or its absence. Offer large uncertain apps for review; do not uninstall solely because metadata is missing. Review related optional content even when the main app has already been removed.

## Package stores, tool downloads, and runtimes

Ask installed tools for their cache/store paths or inspect configuration before assuming defaults. Use native help and dry-runs where supported; a discovery pass must not run a cleaning command. Preserve installed global CLIs, authentication and custom package data.

| Family | Common leads | Required distinction |
| --- | --- | --- |
| npm/npx | `~/.npm/_cacache`, `~/.npm/_npx`, configured npm cache | Separate download objects from per-hash tool installations. MCP/automation workers can execute from npx caches for hours; exclude their exact live entries. |
| Bun, pnpm, Yarn, Deno | `~/.bun/install/cache`, configured pnpm/Yarn stores, `~/Library/Caches/deno` or `~/.cache/deno` | Bun's global tool installation is separate. Check links/reconstruction inputs and preserve current offline-only/custom packages. |
| Python package caches | `~/.cache/uv`, pip's configured cache, Conda installation `pkgs` and archive caches | Extracted package stores can back environments through links. A native prune's selected unused subset differs from the entire store; inspect unregistered environments too. |
| Native/build downloads | `~/Library/Caches/node-gyp`, `ReactNative`, `dotslash`, CocoaPods stores, Clang/Swift module caches | Differentiate downloaded headers, RN Core/Hermes archives and cached DevTools apps from installed workspaces, SDKs and source. Wait for relevant compilation/debugging jobs. |
| Test browsers and automation | `~/Library/Caches/ms-playwright`, Puppeteer/browser-driver downloads, other configured automation homes | Match installed versions and active workers. These are test runtimes, not user browser profiles; browser jobs may run under an IDE or MCP parent. |
| Gradle and language caches | `~/.gradle/{caches,wrapper}`, Go module/build caches, Cargo registry/git caches, Ruby caches, Homebrew downloads | Preserve JDKs, tool binaries, config, local patches and required offline inputs. Distinguish reusable downloads from installed environments. |
| Versioned runtimes | nvm/Volta/asdf/mise installations; `~/.rustup/toolchains`; user and system `Java/JavaVirtualMachines`; `/Library/Frameworks/{Python,Mono}.framework`; Conda environments | Check versions, architecture, defaults, links, project requirements, global tools and active processes. Embedded Android Studio/Xcode/app runtimes are separate dependencies. See the runtime procedure before removal. |
| Per-user macOS caches | Resolve `getconf DARWIN_USER_CACHE_DIR` and `getconf DARWIN_USER_TEMP_DIR`; examine named children such as `clang` or an uninstalled browser helper | Do not hardcode another user's hashed `/var/folders` path or wipe the whole C/T directory. Check the exact owner/product and current handles. |

Do not count all Java/Node/Python versions as recoverable if a retained default or environment needs one. Deleting a package cache, uninstalling an environment, and retiring its interpreter are separate operations.

## Projects, research, devices, and virtual machines

| Family | Discovery approach | Preserve or verify |
| --- | --- | --- |
| Project build/dependency trees | Developer roots, sibling projects, hidden agent/IDE workspaces, generated archives, DerivedData, Pods, node_modules, virtualenvs and platform builds | Check Git tracking, build markers, lockfiles, custom patches and active checkouts. Names such as output/build/dist alone prove nothing. |
| Agent worktrees | `git worktree list --porcelain`, managed worktree roots and nested workspace locations | Inspect dirty/untracked/ignored content and live processes. Preserve unique source/configuration before removing a selected obsolete worktree through Git. Do not delete branches/refs as a side effect. |
| Custom research environments | `~/.local/share`, project output/tools, analysis and experiment runtimes; examples include app-research, microdrama-research, app-dark-patterns and reelshort-research | Separate acquired app packages, extracted copies, emulation runtimes and recreatable dependencies from scripts, credentials, findings and unique evidence. Inspect manifests/README and representative file metadata. |
| Large Git object databases | `git count-objects -vH`, pack/index sizes, read-only object/path inspection for dominant blobs | Explain whether size is reachable history, duplicate loose data, or classified abandoned temporary files. A pack containing old ZIPs or an unreferenced object is not automatically safe to delete. Follow the Git procedure. |
| Media and campaign assets | Large videos/audio, render folders, transcodes, frames, raw footage and downloaded reference/background collections | Explain the actual content and role. Source footage, delivered masters and unique research may remain valuable. Trace dependencies; respect project-wide keeps across other folders and cloud copies. |
| iOS/Android | Registered devices/runtimes, custom AVD homes, SDK images, Xcode build/test output, archives and device-support symbols | Map actual on-disk allocations and retained device requirements. A registration pointing to a 4 KB placeholder is not a large emulator. Shutdown does not establish disposability. |
| Containers and desktop VMs | Docker/Podman/Colima configured data, Claude Desktop VM/scratch disks and similar sandbox homes | Measure allocated blocks, not virtual maximum capacity. Native usage inventories can identify layers/build cache, but volumes, app state and VM disks require their own authorization and dependency review. |
| Models and large toolchains | Hugging Face/Whisper caches, Ollama/LM Studio/model homes, Unity/SDK/editor installations, downloaded research binaries | Distinguish downloadable public weights from custom models, active services and pinned toolchains. Check configured model/SDK locations, links and current task needs. |

For a huge project, provide a decomposition whose categories reconcile with its total without counting nested children twice. Explain surprising categories in ordinary terms—what an acquired package is, what background footage depicts, or why Git retains deleted content. Do not equate all non-product folders with obsolete work.

## Downloads, history, cloud storage, and OS-managed space

- **Downloads/Desktop/Movies and Trash:** inspect large archives/installers and duplicate exports outside Developer. Apply the user's age and last-opened conditions separately. Filesystem atime/mtime can reflect indexing or background work; missing reliable last-use evidence is not proof a file was unopened. Keep current source-media ZIPs unless their removal is authorized and their contents are safely retained. Emptying Trash also deletes its unique contents and needs appropriate scope.
- **Application logs:** inspect selected app log roots and DiagnosticReports by file age, current handles and investigation relevance. Keep recent logs and cleanup/recovery backups. Old diagnostic cleanup does not authorize deleting conversation records or whole Logs directories.
- **Chat/history and SQLite:** classify transcripts, attachments, scratch workspaces and app databases separately from web/code caches. History age limits apply only when authorized; use the format's meaningful conversation/last-activity timestamps. Recent modification or a large database alone says little about disposability. Check actual reusable/free-page space before suggesting compaction; never vacuum a live database casually.
- **Cloud offline copies:** inspect allocated local copies in CloudStorage and provider-specific locations. Use the provider's online-only/eviction action after confirming sync and exclusions. Removing a synced path can delete the cloud copy; a general storage cleanup is not authorization to erase remote data.
- **System Data, snapshots and protected libraries:** identify the owning store rather than treating a macOS category as junk. Inspect local backup/snapshot accounting and Photos/Mail/Messages through supported read-only/native views when needed. Shared snapshot blocks and purgeable space are not guaranteed recovery. Do not disable SIP/privacy controls or delete protected databases to meet a target; report access/measurement gaps.

## Completion and further opportunities

Re-measure shortlisted scopes after earlier batches and remove already completed rows from the current opportunity list. Explain kept defaults, active installations and user exclusions so a future pass does not offer them again as proven junk. Report completed removals separately from conditional opportunities and uninspected areas. Cache payloads may regenerate; preserve exact receipts and use comparisons to distinguish regeneration from an unsuccessful deletion.
