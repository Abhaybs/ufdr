const API_BASE = "http://localhost:8000/api";

const form = document.getElementById("graph-form");
const termInput = document.getElementById("graph-term");
const statusNode = document.getElementById("graph-status");
const graphContainer = document.getElementById("graph-container");
const detailsNode = document.getElementById("graph-details");

let network = null;
let nodesDataset = null;
let edgesDataset = null;
let nodeMetadata = new Map();

function ensureNetwork() {
    if (network) {
        return;
    }

    nodesDataset = new vis.DataSet();
    edgesDataset = new vis.DataSet();

    const options = {
        layout: { improvedLayout: true },
        physics: {
            stabilization: true,
            barnesHut: {
                gravitationalConstant: -3200,
                centralGravity: 0.3,
                springLength: 140,
                springConstant: 0.04,
            },
        },
        nodes: {
            shape: "dot",
            size: 18,
            color: {
                border: "#2563eb",
                background: "#dbeafe",
                highlight: {
                    border: "#1d4ed8",
                    background: "#bfdbfe",
                },
            },
            font: { color: "#1f2937", size: 14 },
        },
        edges: {
            arrows: { to: { enabled: true, scaleFactor: 0.7 } },
            color: { color: "#9ca3af", highlight: "#2563eb" },
            smooth: {
                enabled: true,
                type: "dynamic",
            },
        },
        interaction: {
            hover: true,
            tooltipDelay: 100,
        },
    };

    network = new vis.Network(graphContainer, { nodes: nodesDataset, edges: edgesDataset }, options);

    network.on("selectNode", (params) => {
        const nodeId = params.nodes?.[0];
        if (!nodeId) {
            updateDetails();
            return;
        }
        const metadata = nodeMetadata.get(String(nodeId));
        updateDetails(metadata);
    });

    network.on("deselectNode", () => {
        updateDetails();
    });
}

function formatTooltip(data) {
    if (!data) {
        return "";
    }
    const entries = Object.entries(data)
        .filter(([key]) => key !== "focus")
        .map(([key, value]) => {
            let displayValue = value;
            if (key === "last_seen_source") {
                displayValue = basename(value);
            }
            return `${humanizeKey(key)}: ${displayValue ?? ""}`;
        });
    return entries.join("<br>");
}

function renderGraph(graph) {
    ensureNetwork();

    nodesDataset.clear();
    edgesDataset.clear();
    nodeMetadata = new Map();

    graph.nodes.forEach((node) => {
        const nodeData = node.data || {};
        const displayLabel = nodeData.display_name || node.label;
        nodesDataset.add({
            id: node.id,
            label: displayLabel,
            group: node.group,
            title: formatTooltip(nodeData),
        });
        nodeMetadata.set(String(node.id), {
            id: node.id,
            label: displayLabel,
            display_name: nodeData.display_name || displayLabel,
            ...nodeData,
        });
    });

    graph.edges.forEach((edge) => {
        edgesDataset.add({
            id: edge.id,
            from: edge.source,
            to: edge.target,
            label: edge.label || "",
            title: formatTooltip(edge.data),
        });
    });

    if (graph.focus) {
        graph.focus.forEach((nodeId) => {
            nodesDataset.update({
                id: nodeId,
                color: {
                    border: "#1d4ed8",
                    background: "#2563eb",
                },
                font: { color: "#ffffff" },
            });
        });
    }

    const nodeIds = nodesDataset.getIds();
    if (nodeIds.length > 0) {
        network.fit({ nodes: nodeIds, animation: { duration: 600 } });
    }

    updateDetails();
}

async function searchGraph(term) {
    statusNode.textContent = "Loading graph data...";

    try {
        const response = await fetch(`${API_BASE}/graph/${encodeURIComponent(term)}`);
        if (!response.ok) {
            const error = await response.json().catch(() => ({}));
            throw new Error(error.detail || `Request failed with status ${response.status}`);
        }

        const graph = await response.json();
        renderGraph(graph);
        statusNode.textContent = `Showing ${graph.nodes.length} nodes and ${graph.edges.length} edges.`;
    } catch (error) {
        console.error(error);
        statusNode.textContent = `Error: ${error.message}`;
    }
}

form.addEventListener("submit", (event) => {
    event.preventDefault();
    const term = termInput.value.trim();
    if (!term) {
        statusNode.textContent = "Enter a search term.";
        return;
    }
    searchGraph(term);
});

statusNode.textContent = "Enter a name, phone, or email to explore the graph.";

function updateDetails(metadata) {
    if (!detailsNode) {
        return;
    }

    if (!metadata) {
        detailsNode.innerHTML = "Click a node to see details.";
        return;
    }

    const preferredName = metadata.display_name || metadata.label || metadata.raw_identifier || metadata.id;
    const primaryIdentifier = metadata.raw_identifier || metadata.id || metadata.label;
    const source = metadata.last_seen_source ? basename(metadata.last_seen_source) : "—";

    const lines = [
        `<div class="details-head">${preferredName ?? "Unknown"}</div>`,
        `<div><strong>Identifier</strong>: ${primaryIdentifier ?? "—"}</div>`,
        `<div><strong>Source</strong>: ${source}</div>`,
    ];

    const extras = Object.entries(metadata)
        .filter(([key]) => !["display_name", "label", "raw_identifier", "id", "focus", "last_seen_source"].includes(key))
        .map(([key, value]) => `<div><strong>${humanizeKey(key)}</strong>: ${value ?? ""}</div>`);

    detailsNode.innerHTML = [...lines, ...extras].join("") || "No additional details.";
}

function humanizeKey(key) {
    return key
        .replace(/_/g, " ")
        .replace(/([a-z])([A-Z])/g, "$1 $2")
        .replace(/^./, (ch) => ch.toUpperCase());
}

function basename(path) {
    if (!path) {
        return "";
    }
    const normalized = String(path).replace(/\\/g, "/");
    const segments = normalized.split("/");
    return segments[segments.length - 1] || normalized;
}