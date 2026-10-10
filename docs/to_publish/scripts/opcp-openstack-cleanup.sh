#!/usr/bin/env bash
#
# opcp-openstack-cleanup.sh
#
# version 0.1			09/10/2026
#
# Clean the OPCP platform before VCF deployment:
#   1. Delete all Nova instances deployed on baremetal nodes.
#   2. Disable / clean any software RAID configuration on baremetal nodes.
#   3. Verify that every baremetal node is owned by "admin".
#
# Reference labs:
#   https://opcp-psmc.com/admin/opcp-openstack-first-steps/en/cleanup.html
#   https://opcp-psmc.com/admin/opcp-openstack-first-steps/en/software-raid.html
#
# !!! DESTRUCTIVE !!!  This script deletes running instances and wipes RAID /
# device metadata. Review the dry-run output before running for real.
#
# Usage:
#   ./opcp-openstack-cleanup.sh [options]
#
# Options:
#   -y, --yes             Skip interactive confirmation (non-interactive mode).
#   -n, --dry-run         Show what would be done without changing anything.
#   -o, --owner OWNER     Required owner for nodes (default: admin).
#   -t, --timeout SECONDS Max seconds to wait for a state transition (default: 1800).
#   -i, --interval SEC    Poll interval in seconds (default: 15).
#   -f, --baremetals-file FILE
#                         File listing the baremetal nodes to clean (one per line,
#                         name or UUID; '#' comments and blank lines ignored).
#                         Default: list_of_baremetals_to_clean.txt (if present).
#   -a, --all             Operate on ALL baremetal nodes (skip file / listbox).
#   -x, --exclude "UUID NAME"
#                         Exclude a specific server from the cleanup list. For
#                         safety BOTH the UUID and the name must be given and
#                         must match the same node in 'baremetal node list';
#                         otherwise the script aborts. Repeat -x to exclude
#                         several servers.
#   -h, --help            Show this help and exit.
#
# Node selection:
#   If a baremetals file is found/provided, only the nodes it lists are cleaned.
#   Otherwise (and when not using --all), an interactive listbox is shown so you
#   can pick which baremetal names/UUIDs to clean.
#   Any node matched by --exclude is removed from the final set after selection.
#
set -euo pipefail

# ----------------------------------------------------------------------------
# Defaults
# ----------------------------------------------------------------------------
ASSUME_YES=false
DRY_RUN=false
REQUIRED_OWNER="admin"
WAIT_TIMEOUT=1800
POLL_INTERVAL=15
RAID_STEPS_FILE="/tmp/raid-clean-steps.json"

# Node-selection defaults.
BAREMETALS_FILE=""                                   # explicit file via -f
DEFAULT_BAREMETALS_FILE="list_of_baremetals_to_clean.txt"
SELECT_ALL=false                                     # -a / --all
# Each entry is a "uuid<TAB>name" pair the user asked to exclude (-x / --exclude).
declare -a EXCLUDE_SPECS=()
# Populated by resolve_target_nodes(): one "uuid<TAB>name" entry per selected node.
declare -a TARGET_NODES=()
declare -A TARGET_UUIDS=()                            # uuid -> 1 for quick lookup

# ----------------------------------------------------------------------------
# Colors / logging
# ----------------------------------------------------------------------------
if [[ -t 1 ]]; then
    C_RESET="\033[0m"; C_INFO="\033[0;34m"; C_OK="\033[0;32m"
    C_WARN="\033[0;33m"; C_ERR="\033[0;31m"; C_BOLD="\033[1m"
else
    C_RESET=""; C_INFO=""; C_OK=""; C_WARN=""; C_ERR=""; C_BOLD=""
fi

log()  { echo -e "${C_INFO}[INFO ]${C_RESET} $*"; }
ok()   { echo -e "${C_OK}[ OK  ]${C_RESET} $*"; }
warn() { echo -e "${C_WARN}[WARN ]${C_RESET} $*" >&2; }
err()  { echo -e "${C_ERR}[ERROR]${C_RESET} $*" >&2; }
step() { echo -e "\n${C_BOLD}==> $*${C_RESET}"; }

# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------
usage() {
    sed -n '2,43p' "$0" | sed 's/^# \{0,1\}//'
    exit "${1:-0}"
}

# Run (or echo in dry-run) a mutating OpenStack command.
run() {
    if $DRY_RUN; then
        echo -e "${C_WARN}[DRY-RUN]${C_RESET} $*"
        return 0
    fi
    log "exec: $*"
    "$@"
}

# Prompt for confirmation unless -y was passed.
confirm() {
    local prompt="$1"
    if $ASSUME_YES; then
        return 0
    fi
    local reply
    read -r -p "$(echo -e "${C_WARN}${prompt} [y/N]: ${C_RESET}")" reply
    [[ "$reply" =~ ^[Yy]$ ]]
}

require_cmd() {
    command -v "$1" >/dev/null 2>&1 || { err "Required command '$1' not found in PATH."; exit 1; }
}

# Wait until a baremetal node reaches one of the desired provision states.
# Fails if last_error becomes populated or the timeout is exceeded.
wait_for_provision_state() {
    local node_id="$1"; shift
    local -a targets=("$@")
    local elapsed=0 state last_error

    if $DRY_RUN; then
        warn "[DRY-RUN] would poll node $node_id until state in: ${targets[*]}"
        return 0
    fi

    while true; do
        local json
        json="$(openstack baremetal node show "$node_id" -f json 2>/dev/null || true)"
        state="$(echo "$json" | jq -r '.provision_state // "unknown"')"
        last_error="$(echo "$json" | jq -r '.last_error // empty')"

        for t in "${targets[@]}"; do
            if [[ "$state" == "$t" ]]; then
                ok "Node $node_id reached state '$state'."
                return 0
            fi
        done

        if [[ -n "$last_error" ]]; then
            err "Node $node_id reports last_error: $last_error"
            err "Cleaning/transition failed. Manual investigation required."
            return 1
        fi

        if (( elapsed >= WAIT_TIMEOUT )); then
            err "Timeout (${WAIT_TIMEOUT}s) waiting for node $node_id to reach: ${targets[*]} (current: $state)."
            return 1
        fi

        log "Node $node_id state='$state' (waiting for: ${targets[*]}) ... ${elapsed}s"
        sleep "$POLL_INTERVAL"
        elapsed=$(( elapsed + POLL_INTERVAL ))
    done
}

# ----------------------------------------------------------------------------
# Node selection
# ----------------------------------------------------------------------------
# Fetch all baremetal nodes as "uuid<TAB>name" lines (one per node).
list_all_baremetal_nodes() {
    openstack baremetal node list -f json \
        | jq -r '.[] | "\(.uuid)\t\(.name // "-")"'
}

# Given a user-supplied token (either a UUID or a node name), echo the matching
# "uuid<TAB>name" line from the inventory. Prints nothing if no match is found.
match_node_token() {
    local token="$1"; shift
    local -n _match_inv="$1"
    local entry uuid name
    for entry in "${_match_inv[@]}"; do
        uuid="${entry%%$'\t'*}"
        name="${entry#*$'\t'}"
        if [[ "$token" == "$uuid" || "$token" == "$name" ]]; then
            echo "$entry"
            return 0
        fi
    done
    return 1
}

# Read a baremetals file (one name or UUID per line; '#' comments and blank
# lines ignored) and resolve each entry against the live inventory.
load_nodes_from_file() {
    local file="$1"
    local -n _load_inv="$2"
    local token entry
    log "Reading baremetal selection from file: $file"
    while IFS= read -r token || [[ -n "$token" ]]; do
        token="${token%%#*}"                 # strip inline comments
        token="${token#"${token%%[![:space:]]*}"}"   # ltrim
        token="${token%"${token##*[![:space:]]}"}"   # rtrim
        [[ -z "$token" ]] && continue
        if entry="$(match_node_token "$token" "${!_load_inv}")"; then
            TARGET_NODES+=("$entry")
            TARGET_UUIDS["${entry%%$'\t'*}"]=1
        else
            warn "Entry '$token' from $file does not match any baremetal node. Ignored."
        fi
    done < "$file"
}

# Present an interactive listbox so the user can choose which nodes to clean.
# Accepts space/comma-separated indices, or 'a' for all.
select_nodes_interactive() {
    local -n _sel_inv="$1"
    local n=${#_sel_inv[@]}
    local i entry uuid name

    echo
    echo -e "${C_BOLD}Available baremetal nodes:${C_RESET}"
    printf '  %3s  %-38s  %s\n' "#" "UUID" "NAME"
    printf '  %3s  %-38s  %s\n' "---" "--------------------------------------" "----"
    for (( i=0; i<n; i++ )); do
        entry="${_sel_inv[$i]}"
        uuid="${entry%%$'\t'*}"
        name="${entry#*$'\t'}"
        printf '  %3d  %-38s  %s\n' $(( i + 1 )) "$uuid" "$name"
    done
    echo

    local reply
    read -r -p "$(echo -e "${C_WARN}Select nodes to clean (e.g. '1 3 4', 'a'=all, empty=cancel): ${C_RESET}")" reply
    reply="${reply//,/ }"   # allow comma separation

    if [[ -z "$reply" ]]; then
        return 1
    fi

    if [[ "$reply" == "a" || "$reply" == "A" ]]; then
        for entry in "${_sel_inv[@]}"; do
            TARGET_NODES+=("$entry")
            TARGET_UUIDS["${entry%%$'\t'*}"]=1
        done
        return 0
    fi

    local idx
    for idx in $reply; do
        if ! [[ "$idx" =~ ^[0-9]+$ ]] || (( idx < 1 || idx > n )); then
            warn "Ignoring invalid selection: '$idx'"
            continue
        fi
        entry="${_sel_inv[$(( idx - 1 ))]}"
        TARGET_NODES+=("$entry")
        TARGET_UUIDS["${entry%%$'\t'*}"]=1
    done

    [[ ${#TARGET_NODES[@]} -gt 0 ]]
}

# Resolve the final set of target nodes into TARGET_NODES / TARGET_UUIDS using
# this precedence: --all  >  explicit/default file  >  interactive listbox.
resolve_target_nodes() {
    local -a inventory
    mapfile -t inventory < <(list_all_baremetal_nodes)

    if [[ ${#inventory[@]} -eq 0 ]]; then
        warn "No baremetal nodes found in this OpenStack cloud."
        return 0
    fi

    if $SELECT_ALL; then
        log "Selecting ALL baremetal nodes (--all)."
        local entry
        for entry in "${inventory[@]}"; do
            TARGET_NODES+=("$entry")
            TARGET_UUIDS["${entry%%$'\t'*}"]=1
        done
        apply_exclusions
        return 0
    fi

    # Determine which file to use (explicit -f, else default if it exists).
    local file=""
    if [[ -n "$BAREMETALS_FILE" ]]; then
        if [[ ! -f "$BAREMETALS_FILE" ]]; then
            err "Baremetals file not found: $BAREMETALS_FILE"
            exit 1
        fi
        file="$BAREMETALS_FILE"
    elif [[ -f "$DEFAULT_BAREMETALS_FILE" ]]; then
        file="$DEFAULT_BAREMETALS_FILE"
    fi

    if [[ -n "$file" ]]; then
        load_nodes_from_file "$file" inventory
        if [[ ${#TARGET_NODES[@]} -eq 0 ]]; then
            warn "No valid nodes resolved from $file; falling back to interactive selection."
            select_nodes_interactive inventory || true
        fi
    else
        log "No baremetals file provided; opening interactive selection."
        select_nodes_interactive inventory || true
    fi

    apply_exclusions
}

# Remove from TARGET_NODES / TARGET_UUIDS any node matched by --exclude.
# Each exclude spec must contain BOTH a UUID and a name, and both must point to
# the same node in the live inventory (security double-check). If a spec is
# malformed or does not match a real node, the script aborts to avoid wiping the
# wrong machine.
apply_exclusions() {
    [[ ${#EXCLUDE_SPECS[@]} -eq 0 ]] && return 0

    local -a inventory
    mapfile -t inventory < <(list_all_baremetal_nodes)

    local -A excluded_uuids=()
    local spec tok uuid name entry inv_uuid inv_name found

    for spec in "${EXCLUDE_SPECS[@]}"; do
        uuid=""; name=""
        # Split the spec on whitespace into tokens; the UUID-looking token is the
        # UUID, everything else forms the name.
        for tok in $spec; do
            if [[ "$tok" =~ ^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$ ]]; then
                uuid="$tok"
            else
                name="${name:+$name }$tok"
            fi
        done

        if [[ -z "$uuid" || -z "$name" ]]; then
            err "Invalid --exclude spec: '$spec'. You must provide BOTH a UUID and a name."
            exit 1
        fi

        # Verify UUID and name refer to the SAME node in the live inventory.
        found=false
        for entry in "${inventory[@]}"; do
            inv_uuid="${entry%%$'\t'*}"
            inv_name="${entry#*$'\t'}"
            if [[ "$inv_uuid" == "$uuid" ]]; then
                if [[ "$inv_name" == "$name" ]]; then
                    found=true
                else
                    err "Exclusion mismatch: UUID '$uuid' is node '$inv_name', not '$name'."
                    err "Refusing to continue (safety check failed)."
                    exit 1
                fi
                break
            fi
        done

        if ! $found; then
            err "Exclusion target not found in 'baremetal node list': uuid='$uuid' name='$name'."
            exit 1
        fi

        excluded_uuids["$uuid"]=1
        ok "Excluding server '$name' ($uuid) from cleanup."
    done

    # Rebuild TARGET_NODES / TARGET_UUIDS without the excluded nodes.
    local -a kept=()
    local u
    for entry in "${TARGET_NODES[@]}"; do
        u="${entry%%$'\t'*}"
        if [[ -n "${excluded_uuids[$u]:-}" ]]; then
            unset "TARGET_UUIDS[$u]"
            continue
        fi
        kept+=("$entry")
    done
    TARGET_NODES=("${kept[@]+"${kept[@]}"}")
}

# True if the given node UUID is part of the selected target set.
is_target_node() {
    [[ -n "${TARGET_UUIDS[$1]:-}" ]]
}

# ----------------------------------------------------------------------------
# Parse arguments
# ----------------------------------------------------------------------------
while [[ $# -gt 0 ]]; do
    case "$1" in
        -y|--yes)      ASSUME_YES=true; shift ;;
        -n|--dry-run)  DRY_RUN=true; shift ;;
        -o|--owner)    REQUIRED_OWNER="$2"; shift 2 ;;
        -t|--timeout)  WAIT_TIMEOUT="$2"; shift 2 ;;
        -i|--interval) POLL_INTERVAL="$2"; shift 2 ;;
        -f|--baremetals-file) BAREMETALS_FILE="$2"; shift 2 ;;
        -a|--all)      SELECT_ALL=true; shift ;;
        -x|--exclude)  EXCLUDE_SPECS+=("$2"); shift 2 ;;
        -h|--help)     usage 0 ;;
        *)             err "Unknown option: $1"; usage 1 ;;
    esac
done

# ----------------------------------------------------------------------------
# Pre-flight checks
# ----------------------------------------------------------------------------
step "Pre-flight checks"
require_cmd openstack
require_cmd jq

if [[ -z "${OS_AUTH_URL:-}" && -z "${OS_CLOUD:-}" ]]; then
    warn "Neither OS_AUTH_URL nor OS_CLOUD is set. Make sure your OpenStack"
    warn "credentials are sourced (e.g. 'source openrc.sh') before running."
    if ! confirm "Continue anyway?"; then
        err "Aborted: no credentials detected."
        exit 1
    fi
fi

# Quick connectivity sanity check.
if ! $DRY_RUN; then
    if ! openstack token issue >/dev/null 2>&1; then
        err "Unable to authenticate against OpenStack. Check your credentials."
        exit 1
    fi
    ok "Authenticated against OpenStack."
fi

$DRY_RUN && warn "Running in DRY-RUN mode: no changes will be made."

# ----------------------------------------------------------------------------
# Determine which baremetal nodes to operate on.
# ----------------------------------------------------------------------------
step "Selecting baremetal nodes to clean"
resolve_target_nodes

if [[ ${#TARGET_NODES[@]} -eq 0 ]]; then
    err "No baremetal nodes selected. Nothing to do."
    exit 1
fi

echo
echo -e "${C_BOLD}The following baremetal node(s) will be processed:${C_RESET}"
for entry in "${TARGET_NODES[@]}"; do
    printf '  - %-38s %s\n' "${entry%%$'\t'*}" "${entry#*$'\t'}"
done

echo
echo -e "${C_BOLD}This script will perform DESTRUCTIVE actions on the OPCP platform:${C_RESET}"
echo "  - Delete ALL Nova instances deployed on the selected baremetal nodes"
echo "  - Clear and clean any software RAID configuration on the selected nodes"
echo "  - Erase device metadata as part of cleaning"
echo "  - Verify node ownership is '$REQUIRED_OWNER'"
echo
if ! confirm "Are you sure you want to proceed?"; then
    err "Aborted by user."
    exit 1
fi

# ============================================================================
# PHASE 1 — Delete instances deployed on baremetal nodes
# ============================================================================
step "PHASE 1: Deleting Nova instances running on baremetal"

# Build a map of node UUID -> instance_uuid for nodes that currently host an
# instance. With '-f json' the OpenStack client emits snake_case keys
# (instance_uuid, uuid, name), not the Title Case headers shown in table mode.
# An idle node reports instance_uuid as null OR an empty string, so guard both.
# Only the nodes selected earlier (TARGET_UUIDS) are considered.
mapfile -t NODE_LINES < <(
    openstack baremetal node list -f json \
        | jq -r '.[] | select(.instance_uuid != null and .instance_uuid != "") | "\(.uuid)\t\(.instance_uuid)\t\(.name // "-")"'
)

# Keep only selected target nodes.
_filtered=()
for line in "${NODE_LINES[@]}"; do
    [[ -z "$line" ]] && continue
    if is_target_node "$(echo "$line" | cut -f1)"; then
        _filtered+=("$line")
    fi
done
NODE_LINES=("${_filtered[@]}")

if [[ ${#NODE_LINES[@]} -eq 0 ]]; then
    ok "No selected baremetal node currently hosts an instance. Nothing to delete."
else
    log "Found ${#NODE_LINES[@]} baremetal node(s) hosting an instance:"
    printf '  %s\n' "${NODE_LINES[@]}"

    for line in "${NODE_LINES[@]}"; do
        node_id="$(echo "$line" | cut -f1)"
        instance_id="$(echo "$line" | cut -f2)"
        node_name="$(echo "$line" | cut -f3)"

        step "Node $node_name ($node_id) -> instance $instance_id"

        # Confirm the instance really exists in the server list before deleting.
        if ! $DRY_RUN; then
            if ! openstack server show "$instance_id" >/dev/null 2>&1; then
                warn "Instance $instance_id not found via 'server show'. Skipping delete."
                continue
            fi
        fi

        if confirm "Delete instance $instance_id on node $node_name?"; then
            run openstack server delete "$instance_id"
            log "Waiting for node $node_id to return to 'available'..."
            # After an instance delete the node goes active -> deleting -> cleaning
            # -> available (automatic cleaning), or straight to available.
            wait_for_provision_state "$node_id" "available" "manageable" || \
                warn "Node $node_id did not reach 'available'. Continue manually if needed."
        else
            warn "Skipped deletion of instance $instance_id."
        fi
    done
fi

# ============================================================================
# PHASE 2 — Disable / clean software RAID configuration
# ============================================================================
step "PHASE 2: Disabling and cleaning software RAID configurations"

# Write the clean-steps file used by 'node clean'.
write_raid_steps_file() {
    if $DRY_RUN; then
        warn "[DRY-RUN] would write RAID clean steps to $RAID_STEPS_FILE"
        return 0
    fi
    cat > "$RAID_STEPS_FILE" <<'EOF'
[
  {
    "interface": "raid",
    "step": "delete_configuration"
  },
  {
    "interface": "deploy",
    "step": "erase_devices_metadata"
  }
]
EOF
    ok "Wrote RAID clean steps to $RAID_STEPS_FILE"
}

mapfile -t ALL_NODES < <(printf '%s\n' "${TARGET_NODES[@]}" | cut -f1)

if [[ ${#ALL_NODES[@]} -eq 0 ]]; then
    warn "No baremetal nodes selected."
else
    for node_id in "${ALL_NODES[@]}"; do
        node_json="$(openstack baremetal node show "$node_id" -f json)"
        node_name="$(echo "$node_json" | jq -r '.name // "-"')"
        provision_state="$(echo "$node_json" | jq -r '.provision_state // "unknown"')"
        target_raid="$(echo "$node_json" | jq -c '.target_raid_config // {}')"

        step "Node $node_name ($node_id)"
        log "provision_state=$provision_state  target_raid_config=$target_raid"

        # No RAID config -> nothing to do.
        if [[ "$target_raid" == "{}" || "$target_raid" == "null" || -z "$target_raid" ]]; then
            ok "No RAID configuration on node $node_name. Skipping."
            continue
        fi

        warn "RAID configuration detected on node $node_name."
        if ! confirm "Clear and clean RAID config on node $node_name?"; then
            warn "Skipped RAID cleanup for node $node_name."
            continue
        fi

        # Step 1: move node to manageable (idempotent-ish; skip if already there).
        if [[ "$provision_state" != "manageable" ]]; then
            run openstack baremetal node manage "$node_id"
            wait_for_provision_state "$node_id" "manageable" || {
                err "Could not bring node $node_id to 'manageable'. Skipping."
                continue
            }
        fi

        # Step 2: unset the target RAID configuration.
        run openstack baremetal node unset "$node_id" --target-raid-config

        # Step 3: run the cleaning steps.
        write_raid_steps_file
        run openstack baremetal node clean "$node_id" --clean-steps "$RAID_STEPS_FILE"

        # Step 4: monitor until manageable again.
        log "Monitoring cleaning (manageable -> cleaning -> clean wait -> manageable)..."
        if wait_for_provision_state "$node_id" "manageable"; then
            ok "RAID cleaning completed for node $node_name."
            # Step 5: return node to service.
            if confirm "Return node $node_name to 'available' (provide)?"; then
                run openstack baremetal node provide "$node_id"
                wait_for_provision_state "$node_id" "available" || \
                    warn "Node $node_id did not reach 'available'."
            fi
        else
            err "RAID cleaning did not complete cleanly for node $node_name. Investigate."
        fi
    done
fi

# ============================================================================
# PHASE 3 — Verify node ownership
# ============================================================================
step "PHASE 3: Verifying node ownership is '$REQUIRED_OWNER'"

# The node 'owner' field stores a project ID, not a project name. Resolve the
# required owner (a project name such as 'admin') to its project ID so we can
# compare against and set the node owner using the ID.
REQUIRED_OWNER_ID="$(openstack project show "$REQUIRED_OWNER" -f value -c id 2>/dev/null || true)"
if [[ -z "$REQUIRED_OWNER_ID" ]]; then
    err "Could not resolve project ID for owner '$REQUIRED_OWNER'. Check the project name/credentials."
    exit 1
fi
ok "Resolved required owner '$REQUIRED_OWNER' to project ID '$REQUIRED_OWNER_ID'."

OWNER_PROBLEMS=0
mapfile -t ALL_NODES < <(printf '%s\n' "${TARGET_NODES[@]}" | cut -f1)

for node_id in "${ALL_NODES[@]}"; do
    node_json="$(openstack baremetal node show "$node_id" -f json)"
    node_name="$(echo "$node_json" | jq -r '.name // "-"')"
    owner="$(echo "$node_json" | jq -r '.owner // empty')"

    if [[ "$owner" == "$REQUIRED_OWNER_ID" ]]; then
        ok "Node $node_name ($node_id) owner='$owner' ('$REQUIRED_OWNER')."
    else
        warn "Node $node_name ($node_id) owner='${owner:-<unset>}' (expected '$REQUIRED_OWNER_ID' / '$REQUIRED_OWNER')."
        OWNER_PROBLEMS=$(( OWNER_PROBLEMS + 1 ))
        if confirm "Set owner of node $node_name to '$REQUIRED_OWNER' ($REQUIRED_OWNER_ID)?"; then
            run openstack baremetal node set "$node_id" --owner "$REQUIRED_OWNER_ID"
        fi
    fi
done

# ----------------------------------------------------------------------------
# Summary
# ----------------------------------------------------------------------------
step "Cleanup complete"
if (( OWNER_PROBLEMS > 0 )); then
    warn "$OWNER_PROBLEMS node(s) had an unexpected owner. Re-run verification"
    warn "to confirm all nodes are now owned by '$REQUIRED_OWNER' before VCF deployment."
else
    ok "All nodes are owned by '$REQUIRED_OWNER'."
fi

$DRY_RUN && warn "DRY-RUN finished: no changes were actually made."
exit 0
