import asyncio
import traceback

import dash
import dash_bootstrap_components as dbc
import pandas as pd
from dash import dcc
from dash.dash import no_update
from dash.dependencies import Input, Output, State
from flask_oidc import OpenIDConnect
from keycloak import KeycloakOpenID
from flask import redirect

from app import app
from app.dashutils import (
    build_checklist,
    calculate_metrics_table,
    convert_col_from_usd_to_cad,
    convert_dict_to_radio_item,
    plotly_plot,
    prepare_pnl_df,
)
from app.layout import app_layout
from trade_capture import tc_backend as tcb
from trade_capture.utils import (
    async_pull_from_db,
    convert_pnl_from_usd_to_other,
    format_datamart_data,
    load_data_from_range_type,
)

# instantiate oidc auth for app
oidc = OpenIDConnect(app)

# Configure keycloak client
keycloak_openid = KeycloakOpenID(
    server_url="http://keycloak.ms6mnj5ah.com",
    client_id="flask-app",
    realm_name="soci",
    client_secret_key="makT91mFxi7z9cLBZosDKTQ1fkM0aPPe",
)

dash_app = dash.Dash(
    __name__,
    title="SociVolta Dashboard",
    update_title="Loading...",
    server=app,
    routes_pathname_prefix="/dash/",
    external_stylesheets=[dbc.themes.FLATLY],
    suppress_callback_exceptions=True,
)

# require keycloak oidc login
for view_func in app.view_functions:
    if view_func.startswith(dash_app.config["routes_pathname_prefix"]):
        app.view_functions[view_func] = oidc.require_login(
            app.view_functions[view_func]
        )

dash_app.layout = app_layout


@dash_app.callback(
    Output("check_path_container", "children"),
    [
        Input("pnl", "children"),
        Input("show", "value"),
    ],
)
def update_path_selection(pnl, show):
    dash_app.logger.info("Updating the path checklist for the metrics table")
    if pnl is not None:
        pnl = pd.read_json(pnl, orient="split")
        selection = list(pnl.columns)[1:]
        if "Metrics" not in show:
            checklist = build_checklist(
                "path_selection",
                name="Metric Paths",
                values=selection,
                disabled=True,
                default_all=False,
            )
        else:
            checklist = build_checklist(
                "path_selection",
                name="Metric Paths",
                values=selection,
                disabled=False,
                default_all=True,
            )
        return checklist
    else:
        return no_update


@dash_app.callback(
    Output("display_pull_range", "children"),
    [Input("refresh", "n_clicks"), Input("datetime_range_type", "value")],
)
def on_button_click(n_clicks, datetime_range_type):
    start, end = load_data_from_range_type(datetime_range_type)
    return f"Loading from {start} to {end} (UTC) "


@dash_app.callback(
    Output("plot_type_selector", "children"),
    [
        Input("show", "value"),
    ],
)
def plot_type_selector(show):
    if "Plot" in show:
        bloc = convert_dict_to_radio_item(
            "plot_type_selection",
            {"Cumsum": "cumsum", "Bar": "bar"},
            default_label="Cumsum",
        )
    else:
        bloc = convert_dict_to_radio_item(
            "plot_type_selection", {"Cumsum": "cumsum", "Bar": "bar"}, disabled=True
        )
    return bloc


@dash_app.callback(
    Output("plot_mode_selector", "children"),
    [
        Input("show", "value"),
    ],
)
def plot_type_selector(show):
    if "Plot" in show:
        bloc = convert_dict_to_radio_item(
            "plot_mode_selection",
            {"Price": "PNL", "Volume": "volume"},
            default_label="Price",
        )
    else:
        bloc = convert_dict_to_radio_item(
            "plot_mode_selection", {"Price": "PNL", "Volume": "volume"}, disabled=True
        )
    return bloc


@dash_app.callback(
    [
        Output("form_collapse", "is_open"),
        Output("info_collapse", "is_open"),
    ],
    [Input("datetime_range_type", "value")],
    [State("form_collapse", "is_open"), State("info_collapse", "is_open")],
)
def toggle_fade_for_range_form(n, is_open, is_openn):
    if n != "Range":
        # The range option is not selected
        return False, True
    return True, False


@dash_app.callback(
    [
        Output("pnl_df", "children"),
        Output("pnl", "children"),
        Output("mw", "children"),
        Output("pnl_cad", "children"),
        Output("pnl_mxn", "children"),
        Output("FX_CADUSD", "children"),
        Output("FX_MXNUSD", "children"),
    ],
    [
        Input("submit", "n_clicks"),
        Input("refresh", "n_clicks"),
        Input("datetime_range_type", "value"),
        Input("pnl_source_selection", "value"),
    ],
    [
        State("start", "value"),
        State("end", "value"),
    ],
)
def load_data(n_clicks, nn_clicks, datetime_range_type, pnl_source, the_start, the_end):
    start, end = load_data_from_range_type(datetime_range_type, the_start, the_end)

    dash_app.logger.info(
        f"Loading the data from {start} to {end} (UTC) for {pnl_source}"
    )

    FX_CADUSD_conv, FX_MXNUSD_conv, raw_data = asyncio.run(
        async_pull_from_db(start, end, pnl_source)
    )

    pnl_df = format_datamart_data(raw_data)
    pnl_df_json = pnl_df.to_json(date_format="iso", orient="split")

    mw_per_path = tcb.get_pnl_metrics_data(pnl_df=pnl_df, col="Buy_MW")
    buy_mw_per_path_json = mw_per_path.to_json(date_format="iso", orient="split")
    del mw_per_path

    pnl_per_path = tcb.get_pnl_metrics_data(pnl_df=pnl_df, col="Pnl")
    pnl_per_path_json = pnl_per_path.to_json(date_format="iso", orient="split")

    pnl_per_path_cad = convert_pnl_from_usd_to_other(
        pnl_per_path, FX_conv=FX_CADUSD_conv
    )
    FX_CADUSD_conv_json = FX_CADUSD_conv.to_json(date_format="iso", orient="split")
    pnl_per_path_cad_json = pnl_per_path_cad.to_json(date_format="iso", orient="split")
    del pnl_per_path_cad

    pnl_per_path_mxn = convert_pnl_from_usd_to_other(
        pnl_per_path, FX_conv=FX_MXNUSD_conv
    )
    FX_MXNUSD_conv_json = FX_MXNUSD_conv.to_json(date_format="iso", orient="split")
    pnl_per_path_mxn_json = pnl_per_path_mxn.to_json(date_format="iso", orient="split")
    del pnl_per_path_mxn

    return (
        pnl_df_json,
        pnl_per_path_json,
        buy_mw_per_path_json,
        pnl_per_path_cad_json,
        pnl_per_path_mxn_json,
        FX_CADUSD_conv_json,
        FX_MXNUSD_conv_json,
    )


@dash_app.callback(
    Output("metric", "children"),
    [
        Input("granularity", "value"),
        Input("path_selection", "value"),
        Input("forex", "value"),
        Input("pnl_df", "children"),
        Input("FX_CADUSD", "children"),
        Input("FX_MXNUSD", "children"),
        Input("show", "value"),
    ],
)
def generate_metric_table(
    granularity, path_selection, forex_selection, pnl_df, FX_CADUSD, FX_MXNUSD, show
):
    if "Metrics" in show:
        dash_app.logger.info(
            f'Generating the metrics table in {forex_selection} for a "{granularity}" granularity'
        )
        try:
            df = calculate_metrics_table(
                granularity=granularity,
                path_selection=path_selection,
                forex_selection=forex_selection,
                pnl_df=pnl_df,
                FX_CADUSD=FX_CADUSD,
                FX_MXNUSD=FX_MXNUSD,
            )
            return dbc.Table.from_dataframe(
                df, striped=True, bordered=True, hover=True, responsive=True
            )

        except Exception as e:
            dash_app.logger.exception(e)
            return dbc.Alert(
                f"{e}: {traceback.print_exc()}", color="danger", dismissable=True
            )


@dash_app.callback(
    Output("pplot", "children"),
    [
        Input("granularity", "value"),
        Input("plot_mode_selection", "value"),
        Input("plot_type_selection", "value"),
        Input("forex", "value"),
        Input("pnl", "children"),
        Input("mw", "children"),
        Input("pnl_cad", "children"),
        Input("pnl_mxn", "children"),
        Input("show", "value"),
    ],
)
def generate_price_graph(
    granularity, plot_mode, plot_type, forex_selection, pnl, mw, pnl_cad, pnl_mxn, show
):
    if "Plot" in show:
        plot_mode = plot_mode if plot_mode is not None else "PNL"
        plot_type = plot_type if plot_type is not None else "cumsum"
        dash_app.logger.info(
            f"Generating the {plot_mode.lower()} {plot_type} plot in {forex_selection}"
        )
        try:
            # Load the correct data from memory
            if forex_selection == "USD":
                if plot_mode == "PNL":
                    df = pd.read_json(pnl, orient="split")
                elif plot_mode == "volume":
                    df = pd.read_json(mw, orient="split")
            elif forex_selection == "CAD":
                if plot_mode == "PNL":
                    df = pd.read_json(pnl_cad, orient="split")
                elif plot_mode == "volume":
                    df = pd.read_json(mw, orient="split")
            elif forex_selection == "MXN":
                if plot_mode == "PNL":
                    df = pd.read_json(pnl_mxn, orient="split")
                elif plot_mode == "volume":
                    df = pd.read_json(mw, orient="split")

            return plotly_plot(
                df=df,
                granularity=granularity,
                plot_type=plot_type,
                plot_mode=plot_mode,
                forex_selection=forex_selection,
            )

        except Exception as e:
            dash_app.logger.exception(e)
            return dbc.Alert(
                f"{e}: {traceback.print_exc()}", color="danger", dismissable=True
            )


@dash_app.callback(
    Output("pnl_ca_download-dataframe-csv", "data"),
    [
        Input("pnl_ca_btn_csv", "n_clicks"),
        Input("pnl_df", "children"),
        Input("FX_CADUSD", "children"),
    ],
    prevent_initial_call=True,
)
def download_data_ca(n_clicks, pnl_df, FX_CADUSD):
    pnl_df, FX_conv = prepare_pnl_df(
        granularity="H",
        forex_selection="CAD",
        pnl_df=pnl_df,
        FX_CADUSD=FX_CADUSD,
        FX_MXNUSD=None,
    )
    cols = [
        col
        for col in pnl_df.columns
        if col not in ["PathID", "Source", "HB", "Buy_MW", "Sell_MW"]
    ]
    FX_conv.Date = FX_conv.Date + pd.Timedelta("5H")
    pnl_df = convert_col_from_usd_to_cad(pnl_df, FX_conv=FX_conv, col=cols)
    if n_clicks is not None:
        return dcc.send_data_frame(
            pnl_df.to_csv, "hourly_pnl_data_cad.csv", index=False
        )


@dash_app.callback(
    Output("pnl_us_download-dataframe-csv", "data"),
    [Input("pnl_us_btn_csv", "n_clicks"), Input("pnl_df", "children")],
    prevent_initial_call=True,
)
def download_data_us(n_clicks, pnl_df):
    pnl_df, _ = prepare_pnl_df(
        granularity="H",
        forex_selection="USD",
        pnl_df=pnl_df,
        FX_CADUSD=None,
        FX_MXNUSD=None,
    )
    if n_clicks is not None:
        return dcc.send_data_frame(
            pnl_df.to_csv, "hourly_pnl_data_usd.csv", index=False
        )


@app.route("/logout")
@oidc.require_login
def logout():
    if oidc.user_loggedin:
        refresh_token = oidc.get_refresh_token()
        oidc.logout()
        keycloak_openid.logout(refresh_token)
        return redirect("http://0.0.0.0:5000/dash/")
