import plotly.graph_objects as go


#   レーダーチャート



def build_radar_chart(config, ability_scores):
    """能力スコアをもとにレーダーチャートを生成する。

    Args:
        config (dict): JSONから読み込んだ設定情報。radar_chart.ability_ids / min / max / title を使用する。
        ability_scores (dict): 能力ID をキー、スコア（0〜100）を値とする辞書。

    Returns:
        go.Figure: Plotly のレーダーチャート Figure オブジェクト。
    """
    ability_by_id = {ability["id"]: ability for ability in config["abilities"]}
    ability_ids = config["radar_chart"]["ability_ids"]
    labels = [ability_by_id[ability_id]["name"] for ability_id in ability_ids]
    values = [ability_scores[ability_id] for ability_id in ability_ids]

    labels.append(labels[0])
    values.append(values[0])

    fig = go.Figure(
        data=[
            go.Scatterpolar(
                r=values,
                theta=labels,
                fill="toself",
                name=config["radar_chart"]["title"],
            )
        ]
    )
    fig.update_layout(
        polar={
            "radialaxis": {
                "visible": True,
                "range": [config["radar_chart"]["min"], config["radar_chart"]["max"]],
            }
        },
        showlegend=False,
        margin={"l": 32, "r": 32, "t": 48, "b": 32},
    )

    return fig
