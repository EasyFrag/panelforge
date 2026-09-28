"""Apply explicit manifest bindings for optional model preview nodes."""
from copy import deepcopy


def preview_bindings(manifest, graph):
    bindings = tuple(manifest.get("batch_preview_bypass", ()))
    for binding in bindings:
        node = graph.get(binding["node_id"], {})
        if (node.get("class_type") != "ModelPreviewOverrideKJ"
                or binding.get("output_index") != 0
                or binding.get("input") != "model"
                or not isinstance(node.get("inputs", {}).get("model"), list)):
            raise ValueError("Liaison de preview batch invalide.")
    return bindings


def bypass_previews(graph, bindings):
    for binding in bindings:
        identity = binding["node_id"]
        if identity not in graph:
            continue  # The output pruning may already have removed this branch.
        source = graph[identity]["inputs"][binding["input"]]
        for node in graph.values():
            for name, value in node.get("inputs", {}).items():
                if isinstance(value, list) and value and value[0] == identity:
                    if value != [identity, binding["output_index"]]:
                        raise ValueError("Sortie de preview inattendue.")
                    node["inputs"][name] = deepcopy(source)
        del graph[identity]
    return graph
