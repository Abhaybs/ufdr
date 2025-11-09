// const API_BASE = "http://localhost:8000/api";

// const form = document.getElementById("graph-form");
// const termInput = document.getElementById("graph-term");
// const statusNode = document.getElementById("graph-status");
// const graphContainer = document.getElementById("graph-container");
// const detailsNode = document.getElementById("graph-details");

// let network = null;
// let nodesDataset = null;
// let edgesDataset = null;
// let nodeMetadata = new Map();

// function ensureNetwork() {
//     if (network) {
//         return;
//     }

//     nodesDataset = new vis.DataSet();
//     edgesDataset = new vis.DataSet();

//     const options = {
//         layout: {
//             improvedLayout: true,
//             randomSeed: 8,
//         },
//         physics: {
//             solver: "barnesHut",
//             stabilization: { iterations: 240 },
//             barnesHut: {
//                 gravitationalConstant: -12000,
//                 centralGravity: 0.12,
//                 springLength: 220,
//                 springConstant: 0.03,
//                 avoidOverlap: 0.7,
//             },
//         },
//         nodes: {
//             shape: "dot",
//             size: 22,
//             color: {
//                 border: "#2563eb",
//                 background: "#dbeafe",
//                 highlight: {
//                     border: "#1d4ed8",
//                     background: "#bfdbfe",
//                 },
//             },
//             borderWidth: 2,
//             font: {
//                 color: "#1f2937",
//                 size: 16,
//                 strokeWidth: 6,
//                 strokeColor: "#ffffff",
//             },
//         },
//         edges: {
//             arrows: { to: { enabled: true, scaleFactor: 0.7 } },
//             color: { color: "#9ca3af", highlight: "#2563eb" },
//             width: 2,
//             font: {
//                 size: 12,
//                 align: "horizontal",
//                 background: "rgba(255,255,255,0.8)",
//                 strokeWidth: 0,
//             },
//             smooth: {
//                 enabled: true,
//                 type: "dynamic",
//                 roundness: 0.35,
//             },
//         },
//         interaction: {
//             hover: true,
//             tooltipDelay: 100,
//         },
//     };

//     network = new vis.Network(graphContainer, { nodes: nodesDataset, edges: edgesDataset }, options);

//     network.on("selectNode", (params) => {
//         const nodeId = params.nodes?.[0];
//         if (!nodeId) {
//             updateDetails();
//             return;
//         }
//         const metadata = nodeMetadata.get(String(nodeId));
//         updateDetails(metadata);
//     });

//     network.on("deselectNode", () => {
//         updateDetails();
//     });
// }

// function formatTooltip(data) {
//     if (!data) {
//         return "";
//     }
//     const entries = Object.entries(data)
//         .filter(([key]) => key !== "focus")
//         .map(([key, value]) => {
//             let displayValue = value;
//             if (key === "last_seen_source") {
//                 displayValue = basename(value);
//             }
//             return `${humanizeKey(key)}: ${displayValue ?? ""}`;
//         });
//     return entries.join("<br>");
// }

// function renderGraph(graph) {
//     ensureNetwork();

//     nodesDataset.clear();
//     edgesDataset.clear();
//     nodeMetadata = new Map();

//     graph.nodes.forEach((node) => {
//         const nodeData = node.data || {};
//         const displayLabel = nodeData.display_name || node.label;
//         nodesDataset.add({
//             id: node.id,
//             label: displayLabel,
//             group: node.group,
//             title: formatTooltip(nodeData),
//         });
//         nodeMetadata.set(String(node.id), {
//             id: node.id,
//             label: displayLabel,
//             display_name: nodeData.display_name || displayLabel,
//             ...nodeData,
//         });
//     });

//     graph.edges.forEach((edge) => {
//         edgesDataset.add({
//             id: edge.id,
//             from: edge.source,
//             to: edge.target,
//             label: formatEdgeLabel(edge.label),
//             title: formatTooltip(edge.data),
//         });
//     });

//     if (graph.focus) {
//         graph.focus.forEach((nodeId) => {
//             nodesDataset.update({
//                 id: nodeId,
//                 color: {
//                     border: "#1d4ed8",
//                     background: "#2563eb",
//                 },
//                 font: { color: "#ffffff" },
//             });
//         });
//     }

//     const nodeIds = nodesDataset.getIds();
//     if (nodeIds.length > 0) {
//         network.stopSimulation();
//         network.stabilize(200);
//         network.fit({ nodes: nodeIds, animation: { duration: 600 } });
//     }

//     updateDetails();
// }

// async function searchGraph(term) {
//     statusNode.textContent = "Loading graph data...";

//     try {
//         const response = await fetch(`${API_BASE}/graph/${encodeURIComponent(term)}`);
//         if (!response.ok) {
//             const error = await response.json().catch(() => ({}));
//             throw new Error(error.detail || `Request failed with status ${response.status}`);
//         }

//         const graph = await response.json();
//         renderGraph(graph);
//         statusNode.textContent = `Showing ${graph.nodes.length} nodes and ${graph.edges.length} edges.`;
//     } catch (error) {
//         console.error(error);
//         statusNode.textContent = `Error: ${error.message}`;
//     }
// }

// form.addEventListener("submit", (event) => {
//     event.preventDefault();
//     const term = termInput.value.trim();
//     if (!term) {
//         statusNode.textContent = "Enter a search term.";
//         return;
//     }
//     searchGraph(term);
// });

// statusNode.textContent = "Enter a name, phone, or email to explore the graph.";

// function updateDetails(metadata) {
//     if (!detailsNode) {
//         return;
//     }

//     if (!metadata) {
//         detailsNode.innerHTML = "Click a node to see details.";
//         return;
//     }

//     const preferredName = metadata.display_name || metadata.label || metadata.raw_identifier || metadata.id;
//     const primaryIdentifier = metadata.raw_identifier || metadata.id || metadata.label;
//     const source = metadata.last_seen_source ? basename(metadata.last_seen_source) : "—";

//     const lines = [
//         `<div class="details-head">${preferredName ?? "Unknown"}</div>`,
//         `<div><strong>Identifier</strong>: ${primaryIdentifier ?? "—"}</div>`,
//         `<div><strong>Source</strong>: ${source}</div>`,
//     ];

//     const extras = Object.entries(metadata)
//         .filter(([key]) => !["display_name", "label", "raw_identifier", "id", "focus", "last_seen_source"].includes(key))
//         .map(([key, value]) => `<div><strong>${humanizeKey(key)}</strong>: ${value ?? ""}</div>`);

//     detailsNode.innerHTML = [...lines, ...extras].join("") || "No additional details.";
// }

// function humanizeKey(key) {
//     return key
//         .replace(/_/g, " ")
//         .replace(/([a-z])([A-Z])/g, "$1 $2")
//         .replace(/^./, (ch) => ch.toUpperCase());
// }

// function basename(path) {
//     if (!path) {
//         return "";
//     }
//     const normalized = String(path).replace(/\\/g, "/");
//     const segments = normalized.split("/");
//     return segments[segments.length - 1] || normalized;
// }

// function formatEdgeLabel(label) {
//     if (!label) {
//         return "";
//     }
//     if (/^\d{4}-\d{2}-\d{2}T/.test(label)) {
//         const [date, time] = label.split("T", 2);
//         const displayTime = time ? time.replace("+00:00", " UTC") : "";
//         return `${date}\n${displayTime}`.trim();
//     }
//     return label;
// }
// // const API_BASE = "http://localhost:8000/api";

// // const form = document.getElementById("graph-form");
// // const termInput = document.getElementById("graph-term");
// // const statusNode = document.getElementById("graph-status");
// // const graphContainer = document.getElementById("graph-container");
// // const detailsNode = document.getElementById("graph-details");

// // let network = null;
// // let nodesDataset = null;
// // let edgesDataset = null;
// // let nodeMetadata = new Map();

// // function ensureNetwork() {
// //     if (network) {
// //         return;
// //     }

// //     nodesDataset = new vis.DataSet();
// //     edgesDataset = new vis.DataSet();

// //     const options = {
// //         layout: {
// //             improvedLayout: true,
// //             randomSeed: 8,
// //         },
// //         physics: {
// //             solver: "barnesHut",
// //             stabilization: { iterations: 300 },
// //             barnesHut: {
// //                 gravitationalConstant: -18000,
// //                 centralGravity: 0.15,
// //                 springLength: 280,
// //                 springConstant: 0.02,
// //                 avoidOverlap: 0.85,
// //             },
// //         },
// //         nodes: {
// //             shape: "dot",
// //             size: 28,
// //             color: {
// //                 border: "#2563eb",
// //                 background: "#dbeafe",
// //                 highlight: {
// //                     border: "#1d4ed8",
// //                     background: "#bfdbfe",
// //                 },
// //             },
// //             borderWidth: 2,
// //             font: {
// //                 color: "#1f2937",
// //                 size: 16,
// //                 strokeWidth: 6,
// //                 strokeColor: "#ffffff",
// //             },
// //         },
// //         edges: {
// //             arrows: { to: { enabled: true, scaleFactor: 0.7 } },
// //             color: { color: "#9ca3af", highlight: "#2563eb" },
// //             width: 2,
// //             font: {
// //                 size: 11,
// //                 align: "top",
// //                 background: "rgba(255,255,255,0.9)",
// //                 strokeWidth: 0,
// //                 color: "#4b5563",
// //             },
// //             smooth: {
// //                 enabled: true,
// //                 type: "continuous",
// //                 roundness: 0.5,
// //             },
// //             length: 280,
// //         },
// //         interaction: {
// //             hover: true,
// //             tooltipDelay: 100,
// //         },
// //     };

// //     network = new vis.Network(graphContainer, { nodes: nodesDataset, edges: edgesDataset }, options);

// //     network.on("selectNode", (params) => {
// //         const nodeId = params.nodes?.[0];
// //         if (!nodeId) {
// //             updateDetails();
// //             return;
// //         }
// //         const metadata = nodeMetadata.get(String(nodeId));
// //         updateDetails(metadata);
// //     });

// //     network.on("deselectNode", () => {
// //         updateDetails();
// //     });
// // }

// // function formatTooltip(data) {
// //     if (!data) {
// //         return "";
// //     }
// //     const entries = Object.entries(data)
// //         .filter(([key]) => key !== "focus")
// //         .map(([key, value]) => {
// //             let displayValue = value;
// //             if (key === "last_seen_source") {
// //                 displayValue = basename(value);
// //             }
// //             return `${humanizeKey(key)}: ${displayValue ?? ""}`;
// //         });
// //     return entries.join("<br>");
// // }

// // function renderGraph(graph) {
// //     ensureNetwork();

// //     nodesDataset.clear();
// //     edgesDataset.clear();
// //     nodeMetadata = new Map();

// //     graph.nodes.forEach((node) => {
// //         const nodeData = node.data || {};
// //         const displayLabel = nodeData.display_name || node.label;
// //         nodesDataset.add({
// //             id: node.id,
// //             label: displayLabel,
// //             group: node.group,
// //             title: formatTooltip(nodeData),
// //         });
// //         nodeMetadata.set(String(node.id), {
// //             id: node.id,
// //             label: displayLabel,
// //             display_name: nodeData.display_name || displayLabel,
// //             ...nodeData,
// //         });
// //     });

// //     graph.edges.forEach((edge, index) => {
// //         const formattedLabel = formatEdgeLabel(edge.label);
// //         edgesDataset.add({
// //             id: edge.id || `edge_${index}`,
// //             from: edge.source,
// //             to: edge.target,
// //             label: formattedLabel,
// //             title: formatTooltip(edge.data),
// //         });
// //     });

// //     if (graph.focus) {
// //         graph.focus.forEach((nodeId) => {
// //             nodesDataset.update({
// //                 id: nodeId,
// //                 color: {
// //                     border: "#1d4ed8",
// //                     background: "#2563eb",
// //                 },
// //                 font: { color: "#ffffff" },
// //             });
// //         });
// //     }

// //     const nodeIds = nodesDataset.getIds();
// //     if (nodeIds.length > 0) {
// //         network.stopSimulation();
// //         setTimeout(() => {
// //             network.stabilize(250);
// //             network.fit({ nodes: nodeIds, animation: { duration: 600 } });
// //         }, 100);
// //     }

// //     updateDetails();
// // }

// // async function searchGraph(term) {
// //     statusNode.textContent = "Loading graph data...";

// //     try {
// //         const response = await fetch(`${API_BASE}/graph/${encodeURIComponent(term)}`);
// //         if (!response.ok) {
// //             const error = await response.json().catch(() => ({}));
// //             throw new Error(error.detail || `Request failed with status ${response.status}`);
// //         }

// //         const graph = await response.json();
// //         renderGraph(graph);
// //         statusNode.textContent = `Showing ${graph.nodes.length} nodes and ${graph.edges.length} edges.`;
// //     } catch (error) {
// //         console.error(error);
// //         statusNode.textContent = `Error: ${error.message}`;
// //     }
// // }

// // form.addEventListener("submit", (event) => {
// //     event.preventDefault();
// //     const term = termInput.value.trim();
// //     if (!term) {
// //         statusNode.textContent = "Enter a search term.";
// //         return;
// //     }
// //     searchGraph(term);
// // });

// // statusNode.textContent = "Enter a name, phone, or email to explore the graph.";

// // function updateDetails(metadata) {
// //     if (!detailsNode) {
// //         return;
// //     }

// //     if (!metadata) {
// //         detailsNode.innerHTML = "Click a node to see details.";
// //         return;
// //     }

// //     const preferredName = metadata.display_name || metadata.label || metadata.raw_identifier || metadata.id;
// //     const primaryIdentifier = metadata.raw_identifier || metadata.id || metadata.label;
// //     const source = metadata.last_seen_source ? basename(metadata.last_seen_source) : "—";

// //     const lines = [
// //         `<div class="details-head">${preferredName ?? "Unknown"}</div>`,
// //         `<div><strong>Identifier</strong>: ${primaryIdentifier ?? "—"}</div>`,
// //         `<div><strong>Source</strong>: ${source}</div>`,
// //     ];

// //     const extras = Object.entries(metadata)
// //         .filter(([key]) => !["display_name", "label", "raw_identifier", "id", "focus", "last_seen_source"].includes(key))
// //         .map(([key, value]) => `<div><strong>${humanizeKey(key)}</strong>: ${value ?? ""}</div>`);

// //     detailsNode.innerHTML = [...lines, ...extras].join("") || "No additional details.";
// // }

// // function humanizeKey(key) {
// //     return key
// //         .replace(/_/g, " ")
// //         .replace(/([a-z])([A-Z])/g, "$1 $2")
// //         .replace(/^./, (ch) => ch.toUpperCase());
// // }

// // function basename(path) {
// //     if (!path) {
// //         return "";
// //     }
// //     const normalized = String(path).replace(/\\/g, "/");
// //     const segments = normalized.split("/");
// //     return segments[segments.length - 1] || normalized;
// // }

// // function formatEdgeLabel(label) {
// //     if (!label) {
// //         return "";
// //     }
// //     // For timestamps, show only date and time in compact format
// //     if (/^\d{4}-\d{2}-\d{2}T/.test(label)) {
// //         const [date, time] = label.split("T", 2);
// //         const timeOnly = time ? time.substring(0, 8) : "";
// //         return `${date} ${timeOnly}`;
// //     }
// //     return label;
// // }
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
        layout: {
            improvedLayout: true,
            randomSeed: 42,
            hierarchical: false,
        },
        physics: {
            enabled: true,
            solver: "forceAtlas2Based",
            forceAtlas2Based: {
                gravitationalConstant: -80,
                centralGravity: 0.01,
                springLength: 200,
                springConstant: 0.08,
                avoidOverlap: 1,
            },
            stabilization: {
                enabled: true,
                iterations: 400,
                updateInterval: 25,
            },
        },
        nodes: {
            shape: "dot",
            size: 30,
            color: {
                border: "#2563eb",
                background: "#dbeafe",
                highlight: {
                    border: "#1d4ed8",
                    background: "#bfdbfe",
                },
            },
            borderWidth: 3,
            font: {
                color: "#1f2937",
                size: 15,
                face: "Inter, Arial",
                strokeWidth: 4,
                strokeColor: "#ffffff",
                bold: {
                    color: "#1f2937",
                    size: 15,
                    face: "Inter, Arial",
                }
            },
        },
        edges: {
            arrows: { 
                to: { 
                    enabled: true, 
                    scaleFactor: 0.8,
                    type: "arrow"
                } 
            },
            color: { 
                color: "#94a3b8", 
                highlight: "#3b82f6",
                hover: "#60a5fa"
            },
            width: 2.5,
            font: {
                size: 10,
                align: "horizontal",
                background: "rgba(255,255,255,0.85)",
                strokeWidth: 0,
                color: "#475569",
                face: "Inter, Arial",
                vadjust: -10,
            },
            smooth: {
                enabled: true,
                type: "dynamic",
                roundness: 0.5,
            },
            labelHighlightBold: false,
        },
        interaction: {
            hover: true,
            tooltipDelay: 200,
            hideEdgesOnDrag: true,
            hideEdgesOnZoom: false,
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

    network.on("hoverNode", () => {
        graphContainer.style.cursor = "pointer";
    });

    network.on("blurNode", () => {
        graphContainer.style.cursor = "default";
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
    return entries.join("\n");
}

function renderGraph(graph) {
    ensureNetwork();

    nodesDataset.clear();
    edgesDataset.clear();
    nodeMetadata = new Map();

    graph.nodes.forEach((node) => {
        const nodeData = node.data || {};
        const displayLabel = nodeData.display_name || node.label;
        
        // Create simple tooltip without HTML
        const tooltipText = formatTooltip(nodeData);
        
        nodesDataset.add({
            id: node.id,
            label: displayLabel,
            group: node.group,
            title: tooltipText,
        });
        
        nodeMetadata.set(String(node.id), {
            id: node.id,
            label: displayLabel,
            display_name: nodeData.display_name || displayLabel,
            ...nodeData,
        });
    });

    graph.edges.forEach((edge, index) => {
        const formattedLabel = formatEdgeLabel(edge.label);
        edgesDataset.add({
            id: edge.id || `edge_${index}`,
            from: edge.source,
            to: edge.target,
            label: formattedLabel,
            title: edge.data ? formatTooltip(edge.data) : formattedLabel,
        });
    });

    if (graph.focus) {
        graph.focus.forEach((nodeId) => {
            nodesDataset.update({
                id: nodeId,
                color: {
                    border: "#1d4ed8",
                    background: "#3b82f6",
                },
                font: { color: "#ffffff", strokeColor: "#1d4ed8" },
                borderWidth: 4,
                size: 35,
            });
        });
    }

    const nodeIds = nodesDataset.getIds();
    if (nodeIds.length > 0) {
        setTimeout(() => {
            network.stabilize(300);
            setTimeout(() => {
                network.fit({ 
                    nodes: nodeIds, 
                    animation: { 
                        duration: 800,
                        easingFunction: "easeInOutQuad"
                    } 
                });
            }, 100);
        }, 100);
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
        detailsNode.innerHTML = '<span style="opacity: 0.6;">Click a node to see details.</span>';
        return;
    }

    const preferredName = metadata.display_name || metadata.label || metadata.raw_identifier || metadata.id;
    const primaryIdentifier = metadata.raw_identifier || metadata.id || metadata.label;
    const source = metadata.last_seen_source ? basename(metadata.last_seen_source) : "—";

    const lines = [
        `<div class="details-head">${escapeHtml(preferredName ?? "Unknown")}</div>`,
        `<div><strong>Identifier:</strong> ${escapeHtml(primaryIdentifier ?? "—")}</div>`,
        `<div><strong>Source:</strong> ${escapeHtml(source)}</div>`,
    ];

    const extras = Object.entries(metadata)
        .filter(([key]) => !["display_name", "label", "raw_identifier", "id", "focus", "last_seen_source"].includes(key))
        .map(([key, value]) => `<div><strong>${humanizeKey(key)}:</strong> ${escapeHtml(String(value ?? ""))}</div>`);

    detailsNode.innerHTML = [...lines, ...extras].join("") || "No additional details.";
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
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

function formatEdgeLabel(label) {
    if (!label) {
        return "";
    }
    // For timestamps, show compact format
    if (/^\d{4}-\d{2}-\d{2}T/.test(label)) {
        const [date, time] = label.split("T", 2);
        const timeOnly = time ? time.substring(0, 5) : ""; // Show only HH:MM
        return `${date}\n${timeOnly}`;
    }
    // Limit label length
    if (label.length > 20) {
        return label.substring(0, 17) + "...";
    }
    return label;
}