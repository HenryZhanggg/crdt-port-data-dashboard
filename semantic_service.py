"""Read-only RDF lookup and product selection for the local illustrative demo."""

from copy import deepcopy
from datetime import date, datetime, time, timezone
import json
from pathlib import Path

from rdflib import Graph, Namespace, RDF, RDFS, URIRef


DEMO = Namespace("https://example.invalid/crdt-demo/")
BASE = Path(__file__).resolve().parent


def _id(term):
    return str(term).replace(str(DEMO), "demo:", 1)


def _term(identifier):
    return URIRef(str(DEMO) + identifier[5:]) if identifier.startswith("demo:") else URIRef(identifier)


def _instant(value, end=False):
    if isinstance(value, str):
        value = date.fromisoformat(value) if len(value) == 10 else datetime.fromisoformat(value.replace("Z", "+00:00"))
    if isinstance(value, date) and not isinstance(value, datetime):
        value = datetime.combine(value, time.max if end else time.min)
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _window(start, end):
    bounds = (_instant(start) if start is not None else None,
              _instant(end, end=True) if end is not None else None)
    if all(bounds) and bounds[0] > bounds[1]:
        raise ValueError("Start must be before or equal to end")
    return bounds


def _overlaps(start, end, bounds):
    return ((bounds[0] is None or _instant(end, end=True) >= bounds[0])
            and (bounds[1] is None or _instant(start) <= bounds[1]))


class SemanticDemo:
    """Load fixed local fixtures; no remote parsing or model execution interface."""

    def __init__(self):
        self.graph = Graph().parse(data=(BASE / "ontology/semantic_demo.ttl").read_text(encoding="utf-8"), format="turtle")
        self._data = json.loads((BASE / "data/semantic_demo.json").read_text(encoding="utf-8"))
        self.metadata = deepcopy(self._data["metadata"])
        self.sources = deepcopy(self._data["sources"])
        self.scenarios = deepcopy(self._data["scenarios"])

    def _label(self, term):
        return str(self.graph.value(term, RDFS.label))

    def _entity_type(self, subject):
        return next((kind for kind in self.graph.objects(subject, RDF.type)
                     if _id(kind) in self._data["profiles"]), None)

    def types(self):
        """Return concrete RDF types that have selectable demo objects."""
        kinds = {self._entity_type(subject) for subject in self.graph.subjects(RDF.type)} - {None}
        return [{"uri": _id(kind), "label": self._label(kind)} for kind in sorted(kinds)]

    def entities(self, type_uri=None):
        result = []
        for subject in sorted(set(self.graph.subjects(RDF.type))):
            kind = self._entity_type(subject)
            if kind is None:
                continue
            if type_uri and _term(type_uri) not in self.graph.transitive_objects(kind, RDFS.subClassOf):
                continue
            result.append(self.entity(_id(subject)))
        return result

    def entity(self, entity_id):
        subject = _term(entity_id)
        kind = self._entity_type(subject)
        if kind is None:
            raise KeyError(entity_id)
        return {"entity_id": _id(subject), "name": self._label(subject),
                "type_uri": _id(kind), "type_label": self._label(kind),
                "lat": float(self.graph.value(subject, DEMO.lat)),
                "lon": float(self.graph.value(subject, DEMO.lon)),
                "coordinate_note": str(self.graph.value(subject, DEMO.coordinateNote)),
                "source_ids": sorted(_id(value) for value in self.graph.objects(subject, DEMO.source))}

    def relation_types(self):
        return [{"uri": _id(kind), "label": self._label(kind),
                 "inverse_label": str(self.graph.value(kind, DEMO.inverseLabel))}
                for kind in sorted(self.graph.subjects(RDF.type, RDF.Property))
                if self.graph.value(kind, DEMO.inverseLabel) is not None]

    def relations(self, entity_id=None, relation_type=None, start=None, end=None):
        """Return canonical edges whose validity overlaps the inclusive window."""
        bounds = _window(start, end)
        if entity_id:
            self.entity(entity_id)
        result = []
        for edge in sorted(self.graph.subjects(RDF.type, DEMO.Relation)):
            source = _id(self.graph.value(edge, DEMO.sourceEntity))
            target = _id(self.graph.value(edge, DEMO.targetEntity))
            kind = self.graph.value(edge, DEMO.relationType)
            valid_from = str(self.graph.value(edge, DEMO.validFrom))
            valid_to = str(self.graph.value(edge, DEMO.validTo))
            if entity_id and entity_id not in (source, target):
                continue
            if relation_type and _term(relation_type) != kind:
                continue
            if not _overlaps(valid_from, valid_to, bounds):
                continue
            result.append({"relation_id": _id(edge), "source_id": source, "target_id": target,
                           "relation_type": _id(kind), "relation_label": self._label(kind),
                           "direction": "incoming" if entity_id == target else "outgoing",
                           "evidence_ref": _id(self.graph.value(edge, DEMO.evidenceRef)),
                           "evidence_role": str(self.graph.value(edge, DEMO.evidenceRole)),
                           "valid_from": valid_from, "valid_to": valid_to})
        return result

    def related(self, entity_id, relation_type=None, start=None, end=None):
        result = self.relations(entity_id, relation_type, start, end)
        for edge in result:
            incoming = edge["direction"] == "incoming"
            neighbor = self.entity(edge["source_id"] if incoming else edge["target_id"])
            edge.update(neighbor_id=neighbor["entity_id"], neighbor_name=neighbor["name"],
                        display_relation=str(self.graph.value(_term(edge["relation_type"]), DEMO.inverseLabel))
                        if incoming else edge["relation_label"])
        return result

    def profile(self, entity_id):
        kind = self.entity(entity_id)["type_uri"]
        return {"type_uri": kind, **deepcopy(self._data["profiles"][kind])}

    def products(self, entity_id, view_id, start=None, end=None, scenario_id=None):
        bounds = _window(start, end)
        if view_id not in {tab["id"] for tab in self.profile(entity_id)["tabs"]}:
            return []
        result = []
        for product in self._data["products"]:
            if product["entity_id"] != entity_id or product["view_id"] != view_id:
                continue
            if view_id == "scenario" and scenario_id and product["scenario_id"] != scenario_id:
                continue
            selected = deepcopy(product)
            selected["rows"] = [row for row in selected["rows"] if _overlaps(
                row.get("timestamp", row.get("interval_start")),
                row.get("timestamp", row.get("interval_end")), bounds)]
            if selected["rows"]:
                result.append(selected)
        return result

    def models(self, entity_id):
        kind = self.entity(entity_id)["type_uri"]
        return deepcopy([model for model in self._data["models"] if kind in model["applicability_types"]])
