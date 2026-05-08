# app.py
# =========================================================
# 인천공항 T2 입국장 출구 혼잡 예측 대시보드
#
# 실행:
#   py -m pip install streamlit pandas plotly openpyxl
#   py -m streamlit run app.py
#
# 필요 파일:
#   T2_exit_demand_by_gate_corrected_fixed.xlsx
# =========================================================

import streamlit as st
import pandas as pd
import plotly.graph_objects as go


st.set_page_config(
    page_title="T2 입국장 출구 혼잡 예측",
    layout="wide"
)

st.title("인천공항 T2 입국장 출구 혼잡 예측")
st.markdown("---")


@st.cache_data
def load_data(path):
    df = pd.read_excel(path, sheet_name="10분_출구별")

    possible_time_cols = ["시간", "시간대", "시간(10분 단위)"]
    possible_gate_cols = ["출구", "게이트"]
    possible_people_cols = [
        "총 유입 인원",
        "시간당 총 유입 인원",
        "예상 이용객",
        "통과 인원",
        "예상 교통 이용 인원"
    ]

    time_col = next((c for c in possible_time_cols if c in df.columns), None)
    gate_col = next((c for c in possible_gate_cols if c in df.columns), None)
    people_col = next((c for c in possible_people_cols if c in df.columns), None)

    if time_col is None:
        raise Exception(f"시간 컬럼을 찾을 수 없습니다. 현재 컬럼: {list(df.columns)}")
    if gate_col is None:
        raise Exception(f"출구 컬럼을 찾을 수 없습니다. 현재 컬럼: {list(df.columns)}")
    if people_col is None:
        raise Exception(f"인원 컬럼을 찾을 수 없습니다. 현재 컬럼: {list(df.columns)}")

    df[time_col] = pd.to_datetime(df[time_col])
    df[people_col] = pd.to_numeric(df[people_col], errors="coerce").fillna(0)

    return df, time_col, gate_col, people_col


FILE_PATH = "T2_exit_demand_by_gate_corrected_fixed.xlsx"

try:
    df, time_col, gate_col, people_col = load_data(FILE_PATH)
except FileNotFoundError:
    st.error(
        """
        엑셀 파일을 찾을 수 없습니다.

        app.py와 같은 폴더에 아래 파일을 넣어주세요.

        T2_exit_demand_by_gate_corrected_fixed.xlsx
        """
    )
    st.stop()
except Exception as e:
    st.error(str(e))
    st.stop()


def extract_gate_num(x):
    try:
        return int(str(x).replace("번", "").strip())
    except:
        return 999


df["날짜"] = df[time_col].dt.date
dates = sorted(df["날짜"].unique())

selected_date = st.sidebar.selectbox("날짜 선택", dates)

day_df = df[df["날짜"] == selected_date].copy()

gates = sorted(day_df[gate_col].unique(), key=extract_gate_num)

selected_gates = st.sidebar.multiselect(
    "출구 선택",
    gates,
    default=gates
)

day_df = day_df[day_df[gate_col].isin(selected_gates)].copy()

if day_df.empty:
    st.warning("선택된 조건에 해당하는 데이터가 없습니다.")
    st.stop()


# ---------------------------------------------------------
# 분위수 기반 혼잡도 기준
# ---------------------------------------------------------
q50 = day_df[people_col].quantile(0.50)
q75 = day_df[people_col].quantile(0.75)
q90 = day_df[people_col].quantile(0.90)


def congestion_level(v):
    if v < q50:
        return "여유"
    elif v < q75:
        return "보통"
    elif v < q90:
        return "혼잡"
    else:
        return "매우 혼잡"


def congestion_score(v):
    if v < q50:
        return 1
    elif v < q75:
        return 2
    elif v < q90:
        return 3
    else:
        return 4


st.sidebar.markdown("---")
st.sidebar.subheader("혼잡도 기준")
st.sidebar.write(f"여유: {q50:.1f}명 미만")
st.sidebar.write(f"보통: {q50:.1f}명 이상 ~ {q75:.1f}명 미만")
st.sidebar.write(f"혼잡: {q75:.1f}명 이상 ~ {q90:.1f}명 미만")
st.sidebar.write(f"매우 혼잡: {q90:.1f}명 이상")


available_times = sorted(day_df[time_col].unique())

selected_time = st.sidebar.selectbox(
    "추천 기준 시간 선택",
    available_times,
    format_func=lambda x: pd.to_datetime(x).strftime("%H:%M")
)

current_df = day_df[day_df[time_col] == selected_time].copy()
current_df["혼잡도"] = current_df[people_col].apply(congestion_level)
current_df["혼잡점수"] = current_df[people_col].apply(congestion_score)

current_sorted = current_df.sort_values(people_col)

best_gate = current_sorted.iloc[0]
worst_gate = current_sorted.iloc[-1]


st.subheader("현재 기준 추천")

col1, col2, col3 = st.columns(3)

with col1:
    st.metric(
        label="추천 대기 출구",
        value=str(best_gate[gate_col]),
        delta=f"{int(best_gate[people_col])}명 / {best_gate['혼잡도']}"
    )

with col2:
    st.metric(
        label="가장 혼잡한 출구",
        value=str(worst_gate[gate_col]),
        delta=f"{int(worst_gate[people_col])}명 / {worst_gate['혼잡도']}"
    )

with col3:
    st.metric(
        label="추천 기준 시간",
        value=pd.to_datetime(selected_time).strftime("%H:%M")
    )


st.info(
    f"""
    **자가용 픽업 추천**

    선택한 시간 기준으로 가장 여유로운 곳은 **{best_gate[gate_col]}** 입니다.

    예상 유입 인원은 **{int(best_gate[people_col])}명**이며,  
    선택 날짜 전체 분포 기준 혼잡도는 **{best_gate['혼잡도']}** 입니다.

    따라서 자가용으로 대기하거나 일행을 픽업한다면  
    **{best_gate[gate_col]} 주변이 상대적으로 유리**할 가능성이 높습니다.

    반대로 **{worst_gate[gate_col]}** 은 현재 가장 혼잡할 것으로 예측되므로  
    가능하면 피하는 것이 좋습니다.
    """
)

st.markdown("---")


st.subheader("10분 단위 출구별 유입 인원")

fig = go.Figure()

for gate in selected_gates:
    gate_df = day_df[day_df[gate_col] == gate].sort_values(time_col)

    fig.add_trace(
        go.Scatter(
            x=gate_df[time_col],
            y=gate_df[people_col],
            mode="lines+markers",
            name=str(gate)
        )
    )

fig.update_layout(
    height=650,
    xaxis_title="시간",
    yaxis_title="예상 유입 인원",
    hovermode="x unified",
    template="plotly_white"
)

st.plotly_chart(fig, use_container_width=True)


st.markdown("---")
st.subheader("출구별 혼잡 히트맵")

heat_df = day_df.copy()
heat_df["시각"] = heat_df[time_col].dt.strftime("%H:%M")
heat_df["혼잡점수"] = heat_df[people_col].apply(congestion_score)

pivot = heat_df.pivot_table(
    index=gate_col,
    columns="시각",
    values="혼잡점수",
    aggfunc="mean",
    fill_value=0
)

pivot = pivot.reindex(sorted(pivot.index, key=extract_gate_num))

heatmap = go.Figure(
    data=go.Heatmap(
        z=pivot.values,
        x=pivot.columns,
        y=pivot.index,
        colorscale=[
            [0.00, "#2ca25f"],
            [0.33, "#fee08b"],
            [0.66, "#fdae61"],
            [1.00, "#d7191c"]
        ],
        colorbar=dict(
            title="혼잡도",
            tickvals=[1, 2, 3, 4],
            ticktext=["여유", "보통", "혼잡", "매우 혼잡"]
        ),
        zmin=1,
        zmax=4
    )
)

heatmap.update_layout(
    height=500,
    xaxis_title="시간",
    yaxis_title="출구",
    template="plotly_white"
)

st.plotly_chart(heatmap, use_container_width=True)


st.markdown("---")
st.subheader("출구별 일일 누적 유입 인원")

daily_sum = (
    day_df.groupby(gate_col)[people_col]
    .sum()
    .reset_index()
)

daily_sum["정렬"] = daily_sum[gate_col].apply(extract_gate_num)
daily_sum = daily_sum.sort_values("정렬")

bar = go.Figure()

bar.add_trace(
    go.Bar(
        x=daily_sum[gate_col],
        y=daily_sum[people_col],
        text=daily_sum[people_col].astype(int),
        textposition="auto"
    )
)

bar.update_layout(
    height=500,
    xaxis_title="출구",
    yaxis_title="일일 누적 인원",
    template="plotly_white"
)

st.plotly_chart(bar, use_container_width=True)


st.markdown("---")
st.subheader("혼잡 시간 TOP 10")

top_df = day_df[[time_col, gate_col, people_col]].copy()
top_df["혼잡도"] = top_df[people_col].apply(congestion_level)

top_df = (
    top_df.sort_values(people_col, ascending=False)
    .head(10)
)

top_df[time_col] = top_df[time_col].dt.strftime("%Y-%m-%d %H:%M")

st.dataframe(
    top_df,
    use_container_width=True,
    hide_index=True
)


st.markdown("---")
st.subheader("선택 시간 기준 출구 상태")

status_df = current_df[[gate_col, people_col, "혼잡도"]].copy()
status_df["정렬"] = status_df[gate_col].apply(extract_gate_num)
status_df = status_df.sort_values("정렬").drop(columns=["정렬"])

st.dataframe(
    status_df,
    use_container_width=True,
    hide_index=True
)


with st.expander("원본 데이터 보기"):
    show_df = day_df.copy()
    show_df[time_col] = show_df[time_col].dt.strftime("%Y-%m-%d %H:%M")
    st.dataframe(show_df, use_container_width=True, hide_index=True)


st.caption(
    "혼잡도는 선택한 날짜의 10분 단위 출구별 유입 인원 분포를 기준으로 자동 산정됩니다."
)
