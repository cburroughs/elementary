import json
from functools import reduce
from typing import List, Union

from elementary.monitor.data_monitoring.schema import (
    FilterSchema,
    FiltersSchema,
    ResourceTypeFilterSchema,
    StatusFilterSchema,
)
from elementary.monitor.fetchers.alerts.schema.pending_alerts import (
    PendingModelAlertSchema,
    PendingSourceFreshnessAlertSchema,
    PendingTestAlertSchema,
)
from elementary.utils.log import get_logger

logger = get_logger(__name__)


def filter_alerts(
    alerts: Union[
        List[PendingTestAlertSchema],
        List[PendingModelAlertSchema],
        List[PendingSourceFreshnessAlertSchema],
    ],
    alerts_filter: FiltersSchema = FiltersSchema(),
) -> Union[
    List[PendingTestAlertSchema],
    List[PendingModelAlertSchema],
    List[PendingSourceFreshnessAlertSchema],
]:
    # If the filter is on invocation stuff, it's not relevant to alerts and we return an empty list
    if (
        alerts_filter.invocation_id is not None
        or alerts_filter.invocation_time is not None
        or alerts_filter.last_invocation
    ):
        logger.warning("Invalid filter for alerts: %s", alerts_filter.selector)
        return []  # type: ignore[return-value]

    # If the filter is empty, we want to return all of the alerts
    filtered_alerts = alerts
    filtered_alerts = _filter_alerts_by_tags(filtered_alerts, alerts_filter.tags)
    filtered_alerts = _filter_alerts_by_models(filtered_alerts, alerts_filter.models)
    filtered_alerts = _filter_alerts_by_owners(filtered_alerts, alerts_filter.owners)
    filtered_alerts = _filter_alerts_by_statuses(
        filtered_alerts, alerts_filter.statuses
    )
    filtered_alerts = _filter_alerts_by_resource_types(
        filtered_alerts, alerts_filter.resource_types
    )
    if alerts_filter.node_names:
        filtered_alerts = _filter_alerts_by_node_names(
            filtered_alerts, alerts_filter.node_names
        )

    return filtered_alerts


def _find_common_alerts(
    first_alerts: Union[
        List[PendingTestAlertSchema],
        List[PendingModelAlertSchema],
        List[PendingSourceFreshnessAlertSchema],
    ],
    second_alerts: Union[
        List[PendingTestAlertSchema],
        List[PendingModelAlertSchema],
        List[PendingSourceFreshnessAlertSchema],
    ],
) -> Union[
    List[PendingTestAlertSchema],
    List[PendingModelAlertSchema],
    List[PendingSourceFreshnessAlertSchema],
]:
    first_hashable_alerts = [alert.json(sort_keys=True) for alert in first_alerts]
    second_hashable_alerts = [alert.json(sort_keys=True) for alert in second_alerts]
    common_hashable_alerts = [
        json.loads(alert)
        for alert in list(set(first_hashable_alerts) & set(second_hashable_alerts))
    ]
    common_alert_ids = [alert["id"] for alert in common_hashable_alerts]

    common_alerts = []
    # To handle dedupping common alerts
    alert_ids_already_handled = []

    for alert in [*first_alerts, *second_alerts]:
        if alert.id in common_alert_ids and alert.id not in alert_ids_already_handled:
            common_alerts.append(alert)
            alert_ids_already_handled.append(alert.id)
    return common_alerts


def _filter_alerts_by_tags(
    alerts: Union[
        List[PendingTestAlertSchema],
        List[PendingModelAlertSchema],
        List[PendingSourceFreshnessAlertSchema],
    ],
    tags_filters: List[FilterSchema],
) -> Union[
    List[PendingTestAlertSchema],
    List[PendingModelAlertSchema],
    List[PendingSourceFreshnessAlertSchema],
]:
    if not tags_filters:
        return [*alerts]

    grouped_filtered_alerts_by_tags = []

    # OR filter for each tags_filter's values
    for tags_filter in tags_filters:
        filtered_alerts_by_tags = []
        for alert in alerts:
            if any(tag in (alert.tags or []) for tag in tags_filter.values):
                filtered_alerts_by_tags.append(alert)
        grouped_filtered_alerts_by_tags.append(filtered_alerts_by_tags)

    # AND filter between all tags_filters
    return reduce(_find_common_alerts, grouped_filtered_alerts_by_tags)  # type: ignore[return-value, arg-type]


def _filter_alerts_by_owners(
    alerts: Union[
        List[PendingTestAlertSchema],
        List[PendingModelAlertSchema],
        List[PendingSourceFreshnessAlertSchema],
    ],
    owners_filters: List[FilterSchema],
) -> Union[
    List[PendingTestAlertSchema],
    List[PendingModelAlertSchema],
    List[PendingSourceFreshnessAlertSchema],
]:
    if not owners_filters:
        return [*alerts]

    grouped_filtered_alerts_by_owners = []

    # OR filter for each owners_filter's values
    for owners_filter in owners_filters:
        filtered_alerts_by_owners = []
        for alert in alerts:
            if any(owner in alert.unified_owners for owner in owners_filter.values):
                filtered_alerts_by_owners.append(alert)
        grouped_filtered_alerts_by_owners.append(filtered_alerts_by_owners)

    # AND filter between all owners_filters
    return reduce(_find_common_alerts, grouped_filtered_alerts_by_owners)  # type: ignore[return-value, arg-type]


def _filter_alerts_by_models(
    alerts: Union[
        List[PendingTestAlertSchema],
        List[PendingModelAlertSchema],
        List[PendingSourceFreshnessAlertSchema],
    ],
    models_filters: List[FilterSchema],
) -> Union[
    List[PendingTestAlertSchema],
    List[PendingModelAlertSchema],
    List[PendingSourceFreshnessAlertSchema],
]:
    if not models_filters:
        return [*alerts]

    grouped_filtered_alerts_by_models = []

    # OR filter for each models_filter's values
    for models_filter in models_filters:
        filtered_alerts_by_models = []
        for alert in alerts:
            if any(
                (alert.model_unique_id and alert.model_unique_id.endswith(model))
                for model in models_filter.values
            ):
                filtered_alerts_by_models.append(alert)
        grouped_filtered_alerts_by_models.append(filtered_alerts_by_models)

    # AND filter between all models_filters
    return reduce(_find_common_alerts, grouped_filtered_alerts_by_models)  # type: ignore[return-value, arg-type]


def _filter_alerts_by_node_names(
    alerts: Union[
        List[PendingTestAlertSchema],
        List[PendingModelAlertSchema],
        List[PendingSourceFreshnessAlertSchema],
    ],
    node_names_filters: List[str],
) -> Union[
    List[PendingTestAlertSchema],
    List[PendingModelAlertSchema],
    List[PendingSourceFreshnessAlertSchema],
]:
    if not node_names_filters:
        return [*alerts]

    filtered_alerts = []
    for alert in alerts:
        alert_node_name = None
        if isinstance(alert, PendingTestAlertSchema):
            alert_node_name = alert.test_name
        elif isinstance(alert, PendingModelAlertSchema) or isinstance(
            alert, PendingSourceFreshnessAlertSchema
        ):
            alert_node_name = alert.model_unique_id
        else:
            # Shouldn't happen
            raise Exception(f"Unexpected alert type: {type(alert)}")

        if alert_node_name:
            for node_name in node_names_filters:
                if alert_node_name.endswith(node_name) or node_name.endswith(
                    alert_node_name
                ):
                    filtered_alerts.append(alert)
                    break
    return filtered_alerts  # type: ignore[return-value]


def _filter_alerts_by_statuses(
    alerts: Union[
        List[PendingTestAlertSchema],
        List[PendingModelAlertSchema],
        List[PendingSourceFreshnessAlertSchema],
    ],
    statuses_filters: List[StatusFilterSchema],
) -> Union[
    List[PendingTestAlertSchema],
    List[PendingModelAlertSchema],
    List[PendingSourceFreshnessAlertSchema],
]:
    if not statuses_filters:
        return [*alerts]

    grouped_filtered_alerts_by_statuses = []

    # OR filter for each statuses_filter's values
    for statuses_filter in statuses_filters:
        filtered_alerts_by_statuses = []
        for alert in alerts:
            if any(status == alert.status for status in statuses_filter.values):
                filtered_alerts_by_statuses.append(alert)
        grouped_filtered_alerts_by_statuses.append(filtered_alerts_by_statuses)

    # AND filter between all statuses_filters
    return reduce(_find_common_alerts, grouped_filtered_alerts_by_statuses)  # type: ignore[return-value, arg-type]


def _filter_alerts_by_resource_types(
    alerts: Union[
        List[PendingTestAlertSchema],
        List[PendingModelAlertSchema],
        List[PendingSourceFreshnessAlertSchema],
    ],
    resource_types_filters: List[ResourceTypeFilterSchema],
) -> Union[
    List[PendingTestAlertSchema],
    List[PendingModelAlertSchema],
    List[PendingSourceFreshnessAlertSchema],
]:
    if not resource_types_filters:
        return [*alerts]

    grouped_filtered_alerts_by_resource_types = []

    # OR filter for each resource_types_filter's values
    for resource_types_filter in resource_types_filters:
        filtered_alerts_by_resource_types = []
        for alert in alerts:
            if any(
                resource_type == alert.resource_type.value
                for resource_type in resource_types_filter.values
            ):
                filtered_alerts_by_resource_types.append(alert)
        grouped_filtered_alerts_by_resource_types.append(
            filtered_alerts_by_resource_types
        )

    # AND filter between all resource_types_filters
    return reduce(_find_common_alerts, grouped_filtered_alerts_by_resource_types)  # type: ignore[return-value, arg-type]
