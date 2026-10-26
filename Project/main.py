import os
import shutil
from pathlib import Path
from datetime import datetime
import tkinter as tk
from tkinter import filedialog,messagebox,ttk
import customtkinter as ctk
import pandas as pd
import numpy as np
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4,landscape
from reportlab.lib.styles import getSampleStyleSheet,ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import(
    SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle,
    Image as PDFImage,PageBreak
)
from PIL import Image
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")
FONT = "Segoe UI"
BG = "#100B1D"
SIDEBAR = "#19102B"
PANEL = "#211532"
CARD = "#2B1A42"
CARD_HOVER = "#38204F"
PURPLE = "#A855F7"
PINK = "#F472B6"
ORANGE = "#FB923C"
CYAN = "#67E8F9"
GREEN = "#4ADE80"
RED = "#FB7185"
WHITE = "#F8F5FF"
MUTED = "#B9AFCB"
GRID = "#4A355E"
UPLOAD_FOLDER = Path("Dataset")
REPORT_FOLDER = Path("Reports")
UPLOAD_FOLDER.mkdir(exist_ok=True)
REPORT_FOLDER.mkdir(exist_ok=True)
df = None
filtered_df = None
active_file_name = "No dataset loaded"
chart_canvases = []
forecast_cache = None
def find_column(data,*possible_names):
    if data is None:
        return None
    normalized = {str(col).strip().lower(): col for col in data.columns}
    for name in possible_names:
        key = str(name).strip().lower()
        if key in normalized:
            return normalized[key]
    return None
def get_revenue(data):
    revenue_col = find_column(data, "revenue","sales","total_sales","sales_amount")
    quantity_col = find_column(data,"quantity","units_sold","units")
    price_col = find_column(data,"price","unit_price","selling_price")
    if revenue_col:
        return pd.to_numeric(data[revenue_col],errors="coerce")
    if quantity_col and price_col:
        quantity = pd.to_numeric(data[quantity_col],errors="coerce")
        price = pd.to_numeric(data[price_col],errors="coerce")
        return quantity * price
    return None
def get_date_column(data):
    return find_column(data,"date","order_date","sales_date","transaction_date","invoice_date")
def get_product_column(data):
    return find_column(data, "product", "product_name", "item", "item_name")
def get_region_column(data):
    return find_column(data, "region", "city", "location", "state", "territory")
def get_order_count(data):
    order_col = find_column(data,"order_id","orderid","ordernumber","invoice_id")
    if order_col:
        return int(data[order_col].nunique(dropna=True))
    return int(len(data))
def money(value):
    try:
        if pd.isna(value):
            value = 0
        return f"₹{float(value):,.2f}"
    except (TypeError, ValueError):
        return "N/A"
def safe_filename(name):
    keep = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in name)
    return keep.strip().replace(" ","_") or "sales_report"
def calculate_kpis(data):
    revenue = get_revenue(data)
    if data is None or data.empty or revenue is None:
        return{
            "revenue": 0,"orders":0,"units":0,"aov":0,"profit":None,"margin":None
        }
    revenue_total = float(revenue.fillna(0).sum())
    orders = get_order_count(data)
    quantity_col = find_column(data,"quantity","units_sold","units")
    profit_col = find_column(data,"profit","gross_profit","profit_amount")
    units = (
        float(pd.to_numeric(data[quantity_col],errors="coerce").fillna(0).sum())
        if quantity_col else 0
    )
    profit = (
            float(pd.to_numeric(data[profit_col],errors="coerce").fillna(0).sum())
            if profit_col else None
        )
    margin = (profit/revenue_total*100) if profit is not None and revenue_total else None
    return {
        "revenue":revenue_total,
        "orders":orders,
        "units":units,
        "aov":revenue_total/orders if orders else 0,
        "profit":profit,
        "margin":margin,
    }
root = ctk.CTk()
root.title("Sales Data Analyzer")
root.geometry("1500x920")
root.minsize(1120,740)
root.configure(fg_color=BG)
sidebar = ctk.CTkFrame(root,width=225,corner_radius=0,fg_color=SIDEBAR)
sidebar.pack(side="left",fill="y")
sidebar.pack_propagate(False)
main_area = ctk.CTkFrame(root,fg_color=BG,corner_radius=0)
main_area.pack(side="left",fill="both",expand=True)
def load_icon(filename, size):
    """Load an optional icon; return None when its image file is missing."""
    image_path = Path(filename)
    if not image_path.exists():
        return None
    try:
        pil_image = Image.open(image_path).convert("RGBA")
        return ctk.CTkImage(light_image=pil_image, dark_image=pil_image, size=size)
    except Exception:
        return None

sales_icon = load_icon("sales_icon.png", (42, 42))
logo_frame = ctk.CTkFrame(
    sidebar,
    fg_color="transparent"
)
logo_frame.pack(anchor="w", padx=20, pady=(28, 28))
ctk.CTkLabel(
    logo_frame,
    image=sales_icon,
    text=""
).pack(side="left", padx=(0, 10))
ctk.CTkLabel(
    logo_frame,
    text="SALES\nANALYTICS",
    font=(FONT, 20, "bold"),
    text_color=CYAN,
    justify="left"
).pack(side="left")
page_title=ctk.CTkLabel(main_area,text="Sales & Revenue Dashboard",font=(FONT,28,"bold"),text_color="WHITE")
page_title.pack(anchor="w",padx=25,pady=(20,0))
page_subtitle = ctk.CTkLabel(
    main_area,text="Upload your dataset.",font=(FONT,12),text_color=MUTED
)
page_subtitle.pack(anchor="w",padx=27,pady=(3,12))
pages = {}
for name in ["Dashboard","Data Explorer","Data Quality","Analytics","Forecasting & Insights","PDF Report"]:
    pages[name]=ctk.CTkFrame(main_area,fg_color=BG,corner_radius=0)
def show_page(name):
    for frame in pages.values():
        frame.pack_forget()
    pages[name].pack(fill="both",expand=True)
    page_title.configure(text=name if name!= "Dashboard" else "Sales & Revenue Dashboard")
    page_subtitle.configure(
        text=f"Active dataset: {active_file_name} • {len(df):,} rows"
        if df is not None else "Upload your dataset."
    )
    if name == "Data Explorer":
        refresh_table()
    elif name == "Data Quality":
        refresh_quality_report()
    elif name == "Forecasting & Insights":
        refresh_insights()
    elif name == "PDF Report":
        refresh_pdf_page()
nav_icons = {
    "Dashboard": load_icon("dashboard.png", (20, 20)),
    "Data Explorer": load_icon("explorer.png", (20, 20)),
    "Data Quality": load_icon("quality.png", (20, 20)),
    "Analytics": load_icon("analytics.png", (20, 20)),
    "Forecasting & Insights": load_icon("forecast.png", (20, 20)),
    "PDF Report": load_icon("pdf.png", (20, 20)),
}
def nav_button(label, page):
    icon = nav_icons[page]
    ctk.CTkButton(
        sidebar,
        text=label,
        image=icon,
        compound="left",
        command=lambda: show_page(page),
        anchor="w",
        height=42,
        corner_radius=9,
        fg_color="transparent",
        hover_color=CARD_HOVER,
        text_color=WHITE,
        font=(FONT, 13)
    ).pack(fill="x", padx=12, pady=3)
nav_button("Dashboard", "Dashboard")
nav_button("Data Explorer", "Data Explorer")
nav_button("Data Quality", "Data Quality")
nav_button("Analytics", "Analytics")
nav_button("Forecasting & Insights", "Forecasting & Insights")
nav_button("Generate PDF Report", "PDF Report")
filter_panel = ctk.CTkFrame(pages["Dashboard"],fg_color=PANEL,corner_radius=14)
filter_panel.pack(fill="x",padx=20,pady=(5,10))
ctk.CTkLabel(filter_panel,text="FILTERS",font=(FONT,11,"bold"),text_color=CYAN).grid(row=0,column=0,padx=(14,6),pady=12)
product_combo = ctk.CTkComboBox(filter_panel,values=["All Products"],width=150,command=lambda _:apply_filters())
product_combo.grid(row=0,column=1,padx=6,pady=10)
product_combo.set("All Products")
region_combo = ctk.CTkComboBox(filter_panel, values=["All Regions"], width=150,command=lambda _: apply_filters())
region_combo.grid(row=0, column=2, padx=6, pady=10)
region_combo.set("All Regions")
ctk.CTkLabel(filter_panel,text="From",text_color=MUTED,font=(FONT,11)).grid(row=0,column=3,padx=(10,3),pady=10)
start_date_entry = ctk.CTkEntry(filter_panel, placeholder_text="YYYY-MM-DD", width=115)
start_date_entry.grid(row=0, column=4, padx=3, pady=10)
ctk.CTkLabel(filter_panel, text="To", text_color=MUTED, font=(FONT, 11)).grid(
    row=0, column=5, padx=(6, 3), pady=10)
end_date_entry = ctk.CTkEntry(filter_panel, placeholder_text="YYYY-MM-DD", width=115)
end_date_entry.grid(row=0, column=6, padx=3, pady=10)
ctk.CTkButton(filter_panel,text="Apply",width=70,fg_color=PURPLE,hover_color="#7E22CE",command=lambda:apply_filters()).grid(row=0,column=7,padx=5,pady=10)
ctk.CTkButton(filter_panel, text="Reset", width=70, fg_color="#4A355E",
              hover_color="#62447A", command=lambda: reset_filters()).grid(row=0, column=8, padx=(3, 12), pady=10)
search_panel = ctk.CTkFrame(pages["Dashboard"], fg_color="transparent")
search_panel.pack(fill="x", padx=22, pady=(0, 8))
search_entry = ctk.CTkEntry(search_panel, placeholder_text="Search any value", height=36, font=(FONT, 12))
search_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
ctk.CTkButton(search_panel, text="Search", width=100, fg_color=PURPLE,hover_color="#7E22CE", command=lambda: apply_filters()).pack(side="left")
ctk.CTkButton(search_panel, text="Clear Search", width=110, fg_color="#4A355E",hover_color="#62447A", command=lambda: clear_search()).pack(side="left", padx=(7, 0))
filter_status = ctk.CTkLabel(pages["Dashboard"], text="No dataset loaded", font=(FONT, 11), text_color=MUTED)
filter_status.pack(anchor="w", padx=24, pady=(0, 4))
kpi_frame = ctk.CTkFrame(pages["Dashboard"],fg_color="transparent")
kpi_frame.pack(fill="x",padx=17,pady=3)
def create_kpi_card(parent,title,accent):
    card = ctk.CTkFrame(parent,fg_color=CARD,corner_radius=14,border_width=1,border_color="#56366E")
    ctk.CTkLabel(card,text=title.upper(),font=(FONT,10,"bold"),text_color=MUTED).pack(anchor="w",padx=13,pady=(12,4))
    value = ctk.CTkLabel(card, text="_", font=(FONT, 21, "bold"), text_color=accent)
    value.pack(anchor="w", padx=13, pady=(0, 3))
    change = ctk.CTkLabel(card, text="Waiting for data", font=(FONT, 10), text_color=MUTED)
    change.pack(anchor="w", padx=13, pady=(0, 12))
    return card,value,change
kpi_widgets = [
    create_kpi_card(kpi_frame, "Total Revenue", ORANGE),
    create_kpi_card(kpi_frame, "Total Orders", CYAN),
    create_kpi_card(kpi_frame, "Units Sold", GREEN),
    create_kpi_card(kpi_frame, "Average Order Value", PINK),
    create_kpi_card(kpi_frame, "Total Profit", PURPLE),
]
for i, (card, _, _) in enumerate(kpi_widgets):
    kpi_frame.grid_columnconfigure(i, weight=1, uniform="kpi")
    card.grid(row=0, column=i, padx=4, pady=5, sticky="ew")
dashboard_charts = ctk.CTkScrollableFrame(pages["Dashboard"], fg_color="transparent", corner_radius=0)
dashboard_charts.pack(fill="both", expand=True, padx=18, pady=(4, 12))
explorer_top = ctk.CTkFrame(pages["Data Explorer"], fg_color="transparent")
explorer_top.pack(fill="x", padx=20, pady=10)
explorer_info = ctk.CTkLabel(explorer_top, text="Upload a file to view rows", font=(FONT, 12), text_color=MUTED)
explorer_info.pack(side="left")
ctk.CTkButton(explorer_top, text="Export Filtered CSV", fg_color=PURPLE,command=lambda: export_filtered_csv()).pack(side="right")
table_frame = ctk.CTkFrame(pages["Data Explorer"], fg_color=PANEL, corner_radius=12)
table_frame.pack(fill="both", expand=True, padx=20, pady=(0, 18))
tree = ttk.Treeview(table_frame, show="headings")
tree_y = ttk.Scrollbar(table_frame, orient="vertical", command=tree.yview)
tree_x = ttk.Scrollbar(table_frame, orient="horizontal", command=tree.xview)
tree.configure(yscrollcommand=tree_y.set, xscrollcommand=tree_x.set)
tree.grid(row=0, column=0, sticky="nsew")
tree_y.grid(row=0, column=1, sticky="ns")
tree_x.grid(row=1, column=0, sticky="ew")
table_frame.grid_rowconfigure(0, weight=1)
table_frame.grid_columnconfigure(0, weight=1)
style = ttk.Style()
style.theme_use("clam")
style.configure("Treeview", background="#241832", foreground=WHITE,fieldbackground="#241832", rowheight=28, font=(FONT, 10))
style.configure("Treeview.Heading", background="#49305D", foreground=CYAN,font=(FONT, 10, "bold"), relief="flat")
style.map("Treeview", background=[("selected", PURPLE)], foreground=[("selected", WHITE)])
quality_text = ctk.CTkTextbox(pages["Data Quality"], font=(FONT, 13), fg_color=CARD, text_color=WHITE, corner_radius=12)
quality_text.pack(fill="both", expand=True, padx=22, pady=18)
analytics_controls = ctk.CTkFrame(pages["Analytics"], fg_color=PANEL, corner_radius=12)
analytics_controls.pack(fill="x", padx=20, pady=15)
def control_field(parent, label, values, width=180):
    box = ctk.CTkFrame(parent, fg_color="transparent")
    box.pack(side="left", padx=8, pady=10)
    ctk.CTkLabel(box, text=label, text_color=MUTED, font=(FONT, 11, "bold")).pack(anchor="w", pady=(0, 5))
    combo = ctk.CTkComboBox(box, values=values, width=width)
    combo.pack()
    return combo
chart_title_entry = ctk.CTkEntry(analytics_controls, width=190, placeholder_text="Chart title")
chart_title_entry.pack(side="left", padx=8, pady=26)
chart_type_combo = control_field(analytics_controls, "Chart type",["Bar", "Line", "Pie", "Scatter", "Histogram"], 140)
x_combo = control_field(analytics_controls, "X-axis / Category", ["Upload data first"], 180)
y_combo = control_field(analytics_controls, "Y-axis / Value", ["None"], 180)
ctk.CTkButton(
    analytics_controls, text="Generate Chart", fg_color=PURPLE,
    hover_color="#7E22CE", command=lambda: generate_custom_chart()
).pack(side="left", padx=10, pady=26)
custom_chart_holder = ctk.CTkFrame(pages["Analytics"], fg_color=CARD, corner_radius=12)
custom_chart_holder.pack(fill="both", expand=True, padx=20, pady=(0, 18))
insights_text = ctk.CTkTextbox(pages["Forecasting & Insights"], font=(FONT, 13), fg_color=CARD, text_color=WHITE, corner_radius=12)
insights_text.pack(fill="x", padx=22, pady=18)
forecast_chart_holder = ctk.CTkFrame(pages["Forecasting & Insights"], fg_color="transparent", height=280)
forecast_chart_holder.pack(fill="x", padx=22, pady=(0, 16))
pdf_info = ctk.CTkTextbox(pages["PDF Report"], font=(FONT, 13), fg_color=CARD, text_color=WHITE, corner_radius=12, height=220)
pdf_info.pack(fill="x", padx=22, pady=18)
ctk.CTkButton(
    pages["PDF Report"], text="Generate PDF Report", font=(FONT, 14, "bold"),
    height=46, fg_color=PURPLE, hover_color="#7E22CE",
    command=lambda: generate_pdf_report()
).pack(anchor="w", padx=22, pady=(0, 15))
def create_chart(data, chart_type, x_column, y_column=None, title="Sales Chart"):
    fig = Figure(figsize=(7.2, 4.2), dpi=110, facecolor=CARD)
    ax = fig.add_subplot(111)
    ax.set_facecolor(CARD)
    ax.tick_params(colors=WHITE, labelsize=8)
    ax.xaxis.label.set_color(MUTED)
    ax.yaxis.label.set_color(MUTED)
    ax.title.set_color(WHITE)
    for spine in ax.spines.values():
        spine.set_color(GRID)
    ax.grid(axis="y", color=GRID, alpha=0.35)
    chart_type = chart_type.lower()
    if chart_type == "bar":
        if y_column:
            work = data[[x_column, y_column]].copy()
            work[y_column] = pd.to_numeric(work[y_column], errors="coerce")
            grouped = work.dropna().groupby(x_column)[y_column].sum().sort_values(ascending=False).head(12)
            ax.bar(grouped.index.astype(str), grouped.values, color=ORANGE, edgecolor=PINK, linewidth=0.6)
            ax.set_ylabel(y_column)
        else:
            grouped = data[x_column].astype(str).value_counts().head(12)
            ax.bar(grouped.index, grouped.values, color=PURPLE)
            ax.set_ylabel("Record count")
        ax.set_xlabel(x_column)
        ax.tick_params(axis="x", rotation=25)
    elif chart_type == "line":
        if not y_column:
            raise ValueError("Choose a numeric Y-axis column for a line chart.")
        work = data[[x_column, y_column]].copy()
        work[y_column] = pd.to_numeric(work[y_column], errors="coerce")
        grouped = work.dropna().groupby(x_column)[y_column].sum()
        parsed_dates = pd.to_datetime(grouped.index, errors="coerce")
        if len(parsed_dates) and parsed_dates.notna().all():
            grouped.index = parsed_dates
            grouped = grouped.sort_index()
        ax.plot(grouped.index.astype(str), grouped.values, color=ORANGE,marker="o", markersize=4, linewidth=2.4)
        ax.fill_between(range(len(grouped)), grouped.values, alpha=0.12, color=PINK)
        ax.set_xlabel(x_column)
        ax.set_ylabel(y_column)
        ax.tick_params(axis="x", rotation=25)
    elif chart_type == "pie":
        if y_column:
            work = data[[x_column, y_column]].copy()
            work[y_column] = pd.to_numeric(work[y_column], errors="coerce")
            grouped = work.dropna().groupby(x_column)[y_column].sum().sort_values(ascending=False).head(8)
        else:
            grouped = data[x_column].astype(str).value_counts().head(8)
        grouped = grouped[grouped > 0]
        if grouped.empty:
            raise ValueError("There are no positive values available for a pie chart.")
        wedges, _, _ = ax.pie(
            grouped.values, labels=grouped.index.astype(str), autopct="%1.0f%%",startangle=90, textprops={"color": WHITE, "fontsize": 8},
            colors=[PURPLE, PINK, ORANGE, CYAN, GREEN, "#C084FC", "#F9A8D4", "#FDBA74"]
        )
        for wedge, exact_value in zip(wedges, grouped.values):
            wedge._exact_value = float(exact_value)
    elif chart_type == "scatter":
        if not y_column:
            raise ValueError("Choose a numeric Y-axis column for a scatter chart.")
        x_values = pd.to_numeric(data[x_column], errors="coerce")
        y_values = pd.to_numeric(data[y_column], errors="coerce")
        points = pd.DataFrame({"x": x_values, "y": y_values}).dropna()
        ax.scatter(points["x"], points["y"], color=CYAN, alpha=0.75, edgecolors=PINK, linewidths=0.3)
        ax.set_xlabel(x_column)
        ax.set_ylabel(y_column)
    elif chart_type == "histogram":
        values = pd.to_numeric(data[x_column], errors="coerce").dropna()
        if values.empty:
            raise ValueError("The selected column has no numeric values for a histogram.")
        ax.hist(values, bins=15, color=PURPLE, edgecolor=PINK, alpha=0.95)
        ax.set_xlabel(x_column)
        ax.set_ylabel("Frequency")
    else:
        raise ValueError("Unsupported chart type.")
    ax.set_title(title, fontsize=12, fontweight="bold", pad=12)
    tooltip = ax.annotate(
        "", xy=(0, 0), xytext=(12, 12), textcoords="offset points",bbox=dict(boxstyle="round,pad=0.45", fc="#160D25", ec=CYAN, alpha=0.97),color=WHITE, fontsize=9,arrowprops=dict(arrowstyle="->", color=CYAN)
    )
    tooltip.set_visible(False)
    hover_bars = []
    for container in ax.containers:
        for patch in container:
            hover_bars.append(patch)
    hover_wedges = list(ax.patches) if chart_type == "pie" else []
    hover_lines = list(ax.lines)
    def show_hover(event):
        if event.inaxes != ax:
            if tooltip.get_visible():
                tooltip.set_visible(False)
                fig.canvas.draw_idle()
            return
        found = False
        for bar in hover_bars:
            contains, _ = bar.contains(event)
            if contains:
                value = bar.get_height()
                x_position = bar.get_x() + bar.get_width() / 2
                y_position = bar.get_y() + value
                category_index = int(round(x_position))
                category = ""
                if chart_type in ("bar", "line") and ax.get_xticklabels():
                    labels = [label.get_text() for label in ax.get_xticklabels()]
                    if 0 <= category_index < len(labels):
                        category = labels[category_index]
                tooltip.xy = (x_position, y_position)
                tooltip.set_text(f"{category}\n{y_column or 'Count'}: {value:,.2f}")
                tooltip.set_visible(True)
                found = True
                break
        if not found and hover_wedges:
            for index, wedge in enumerate(hover_wedges):
                contains, _ = wedge.contains(event)
                if contains:
                    category = wedge.get_label()
                    value = wedge.theta2 - wedge.theta1
                    tooltip.xy = (event.xdata, event.ydata)
                    tooltip.set_text(f"{category}\nShare: {value / 360 * 100:.2f}%")
                    tooltip.set_visible(True)
                    found = True
                    break
        if not found:
            for line in hover_lines:
                contains, details = line.contains(event)
                if contains and len(details.get("ind", [])):
                    index = int(details["ind"][0])
                    x_data = line.get_xdata()
                    y_data = line.get_ydata()
                    tooltip.xy = (x_data[index], y_data[index])
                    tooltip.set_text(f"{x_data[index]}\n{y_column or 'Value'}: {y_data[index]:,.2f}")
                    tooltip.set_visible(True)
                    found = True
                    break
        if not found:
            tooltip.set_visible(False)
        fig.canvas.draw_idle()
    fig._hover_callback_id = fig.canvas.mpl_connect("motion_notify_event", show_hover)
    fig.tight_layout()
    return fig
def embed_chart(parent, figure):
    canvas = FigureCanvasTkAgg(figure, master=parent)
    canvas.draw()
    canvas.get_tk_widget().pack(fill="both", expand=True, padx=5, pady=5)
    return canvas
def clear_frame(frame):
    for widget in frame.winfo_children():
        widget.destroy()
def refresh_dashboard_charts():
    """Build a clean 2-by-2 dashboard with four useful sales charts."""
    clear_frame(dashboard_charts)

    if filtered_df is None or filtered_df.empty:
        ctk.CTkLabel(
            dashboard_charts, text="Upload data to display your sales dashboard.",
            text_color=MUTED, font=(FONT, 14)).grid(row=0, column=0, columnspan=2, pady=35)
        return
    revenue = get_revenue(filtered_df)
    if revenue is None:
        ctk.CTkLabel(
            dashboard_charts,
            text="Revenue charts need a Revenue/Sales column or both Quantity and Price columns.",
            text_color=RED, font=(FONT, 13)
        ).grid(row=0, column=0, columnspan=2, pady=35)
        return
    work = filtered_df.copy()
    work["_Dashboard_Revenue"] = pd.to_numeric(revenue, errors="coerce").fillna(0)
    dashboard_charts.grid_columnconfigure(0, weight=1, uniform="dashboard_chart")
    dashboard_charts.grid_columnconfigure(1, weight=1, uniform="dashboard_chart")
    def add_chart(row, column, title, chart_kind, x_col, y_col=None, span=1):
        card = ctk.CTkFrame(
            dashboard_charts, fg_color=CARD, corner_radius=16,
            border_width=1, border_color="#56366E"
        )
        card.grid(
            row=row, column=column, columnspan=span,
            padx=7, pady=7, sticky="nsew"
        )
        card.grid_propagate(False)
        card.configure(height=320)
        fig = create_chart(work, chart_kind, x_col, y_col, title)
        # A slightly smaller figure lets the whole chart fit inside each card.
        fig.set_size_inches(5.0 if span == 1 else 10.2, 2.75, forward=True)
        embed_chart(card, fig)
    product_col = get_product_column(work)
    region_col = get_region_column(work)
    date_col = get_date_column(work)
    quantity_col = find_column(work, "Quantity", "Qty", "Units Sold", "Unit Sold", "Units")
    category_col = find_column(work, "Category", "Product Category", "Segment", "Department")
    order_col = find_column(work, "Order ID", "Order_ID", "OrderID", "Invoice", "Invoice ID",
                            "Transaction ID", "Order Number")
    if product_col:
        add_chart(0, 0, "Revenue by Product", "bar",product_col, "_Dashboard_Revenue")
    else:
        add_chart(0, 0, "Revenue Distribution", "bar","_Dashboard_Revenue", "_Dashboard_Revenue")
    if region_col:
        add_chart(0, 1, "Revenue by Region", "pie",region_col, "_Dashboard_Revenue")
    elif category_col:
        add_chart(0, 1, "Revenue by Category", "pie",category_col, "_Dashboard_Revenue")
    else:
        add_chart(0, 1, "Revenue Distribution", "pie",product_col or "_Dashboard_Revenue", "_Dashboard_Revenue")
    if date_col:
        date_work = work.copy()
        date_work["_Dashboard_Date"] = pd.to_datetime(date_work[date_col], errors="coerce")
        date_work = date_work.dropna(subset=["_Dashboard_Date"])
        if not date_work.empty:
            date_work["_Dashboard_Month"] = (
                date_work["_Dashboard_Date"].dt.to_period("M").astype(str)
            )
            card = ctk.CTkFrame(
                dashboard_charts, fg_color=CARD, corner_radius=16,border_width=1, border_color="#56366E"
            )
            card.grid(row=1, column=0, padx=7, pady=7, sticky="nsew")
            card.configure(height=320)
            fig = create_chart(
                date_work, "line", "_Dashboard_Month", "_Dashboard_Revenue","Monthly Revenue Trend"
            )
            fig.set_size_inches(5.0, 2.75, forward=True)
            embed_chart(card, fig)
        else:
            add_chart(1, 0, "Revenue by Product", "bar",product_col or region_col or "_Dashboard_Revenue", "_Dashboard_Revenue")
    else:
        breakdown = category_col or region_col or product_col
        add_chart(1, 0, "Revenue by " + str(breakdown), "bar",breakdown, "_Dashboard_Revenue")
    if product_col and quantity_col:
        add_chart(1, 1, "Units Sold by Product", "bar",product_col, quantity_col)
    elif region_col and order_col:
        counts = work.groupby(region_col)[order_col].nunique().reset_index(name="_Unique_Orders")
        card = ctk.CTkFrame(
            dashboard_charts, fg_color=CARD, corner_radius=16,
            border_width=1, border_color="#56366E"
        )
        card.grid(row=1, column=1, padx=7, pady=7, sticky="nsew")
        card.configure(height=320)
        fig = create_chart(counts, "bar", region_col, "_Unique_Orders", "Orders by Region")
        fig.set_size_inches(5.0, 2.75, forward=True)
        embed_chart(card, fig)
    elif category_col:
        add_chart(1, 1, "Revenue by Category", "bar",category_col, "_Dashboard_Revenue")
    elif region_col:
        add_chart(1, 1, "Revenue by Region", "bar",region_col, "_Dashboard_Revenue")
    else:
        add_chart(1, 1, "Revenue by Product", "bar",product_col or "_Dashboard_Revenue", "_Dashboard_Revenue")
def update_kpis(data):
    kpis = calculate_kpis(data)
    values = [
        money(kpis["revenue"]),
        f'{kpis["orders"]:,}',
        f'{kpis["units"]:,.0f}',
        money(kpis["aov"]),
        money(kpis["profit"]) if kpis["profit"] is not None else "Not available",
    ]
    notes = [
        "Revenue in selected data",
        "Unique orders where Order ID exists",
        "Quantity / units sold",
        "Revenue divided by orders",
        f'Margin: {kpis["margin"]:.2f}%' if kpis["margin"] is not None else "Profit column not found",
    ]
    for widget, value, note in zip(kpi_widgets, values, notes):
        _, value_label, note_label = widget
        value_label.configure(text=value)
        note_label.configure(text=note)       
def apply_filters():
    global filtered_df
    if df is None:
        return
    result = df.copy()
    product_col = get_product_column(result)
    region_col = get_region_column(result)
    selected_product = product_combo.get()
    selected_region = region_combo.get()
    if product_col and selected_product != "All Products":
        result = result[result[product_col].astype(str) == selected_product]
    if region_col and selected_region != "All Regions":
        result = result[result[region_col].astype(str) == selected_region]
    date_col = get_date_column(result)
    start_text = start_date_entry.get().strip()
    end_text = end_date_entry.get().strip()
    if date_col and (start_text or end_text):
        dates = pd.to_datetime(result[date_col], errors="coerce")
        if start_text:
            try:
                start_date = pd.to_datetime(start_text, errors="raise")
                result = result[dates >= start_date]
                dates = pd.to_datetime(result[date_col], errors="coerce")
            except (ValueError, TypeError):
                messagebox.showwarning("Invalid start date", "Use YYYY-MM-DD, for example 2026-10-01.")
                return
        if end_text:
            try:
                end_date = pd.to_datetime(end_text, errors="raise")
                # Include the entire end date, even when the data contains timestamps.
                result = result[dates < end_date + pd.Timedelta(days=1)]
            except (ValueError, TypeError):
                messagebox.showwarning("Invalid end date", "Use YYYY-MM-DD, for example 2026-10-31.")
                return
    elif start_text or end_text:
        messagebox.showinfo("Date filter unavailable", "No recognizable date column was found in this dataset.")
    query = search_entry.get().strip().casefold()
    if query:
        matches = result.astype(str).apply(lambda column: column.str.casefold().str.contains(query, na=False, regex=False)).any(axis=1)
        result = result[matches]
    filtered_df = result.copy()
    update_kpis(filtered_df)
    refresh_dashboard_charts()
    filter_status.configure(text=f"Showing {len(filtered_df):,} of {len(df):,} rows")
    if pages["Data Explorer"].winfo_ismapped():
        refresh_table()
    if pages["Forecasting & Insights"].winfo_ismapped():
        refresh_insights()
def reset_filters():
    product_combo.set("All Products")
    region_combo.set("All Regions")
    start_date_entry.delete(0, "end")
    end_date_entry.delete(0, "end")
    search_entry.delete(0, "end")
    apply_filters()      
def clear_search():
    search_entry.delete(0, "end")
    apply_filters()
def configure_filter_values(data):
    product_col = get_product_column(data)
    region_col = get_region_column(data)
    products = sorted(data[product_col].dropna().astype(str).unique()) if product_col else []
    regions = sorted(data[region_col].dropna().astype(str).unique()) if region_col else []
    product_combo.configure(values=["All Products"] + products)
    region_combo.configure(values=["All Regions"] + regions)
    product_combo.set("All Products")
    region_combo.set("All Regions")  
def refresh_table():
    for item in tree.get_children():
        tree.delete(item)
    if filtered_df is None:
        explorer_info.configure(text="Upload a file to view rows.")
        return
    columns = list(filtered_df.columns)
    tree["columns"] = columns
    for col in columns:
        tree.heading(col, text=str(col))
        tree.column(col, width=130, minwidth=80, anchor="center")
    for _, row in filtered_df.head(100).iterrows():
        values = ["" if pd.isna(value) else str(value) for value in row]
        tree.insert("", "end", values=values)
    explorer_info.configure(text=f"{len(filtered_df):,} matching rows • Showing first {min(len(filtered_df), 100):,}"
    )  
def make_quality_report(data):
    findings = []
    if data is None:
        return ["No dataset has been uploaded yet."]
    findings.append(f"DATA QUALITY REPORT — {active_file_name}")
    findings.append("=" * 55)
    findings.append(f"Rows: {len(data):,}")
    findings.append(f"Columns: {len(data.columns):,}")
    findings.append(f"Exact duplicate rows: {int(data.duplicated().sum()):,}")
    findings.append(f"Missing cells in total: {int(data.isna().sum().sum()):,}")
    findings.append("") 
    missing = data.isna().sum()
    missing = missing[missing > 0].sort_values(ascending=False)
    findings.append("MISSING VALUES BY COLUMN")
    if missing.empty:
        findings.append("  ✓ No missing cells found.")
    else:
        for col, count in missing.items():
            findings.append(f"  • {col}: {count:,} missing ({count / len(data) * 100:.1f}%)")
    findings.append("")
    findings.append("DATA TYPE SUMMARY")
    for col, dtype in data.dtypes.items():
        findings.append(f"  • {col}: {dtype}")
    numeric = data.select_dtypes(include="number")
    negative_columns = [col for col in numeric.columns if (numeric[col] < 0).any()]
    findings.append("")
    findings.append("NEGATIVE NUMERIC VALUES — REVIEW, NOT AUTOMATICALLY ERRORS")
    if negative_columns:
        for col in negative_columns:
            count = int((numeric[col] < 0).sum())
            findings.append(f"  • {col}: {count:,} negative values")
    else:
        findings.append("  ✓ No negative numeric values found.")
    date_col = get_date_column(data)
    findings.append("")
    findings.append("DATE VALIDATION")
    if date_col:
        parsed = pd.to_datetime(data[date_col], errors="coerce")
        invalid_count = int((parsed.isna() & data[date_col].notna()).sum())
        findings.append(f"  • Date column: {date_col}")
        findings.append(f"  • Invalid non-empty dates: {invalid_count:,}")
    else:
        findings.append("  • No recognizable date column was found.")
    findings.append("")
    findings.append("ANALYSIS READINESS")
    if get_revenue(data) is not None:
        findings.append("  ✓ Revenue analysis is possible.")
    else:
        findings.append("  ! Need a Revenue/Sales column or both Quantity and Price columns.")
    findings.append("")
    findings.append("Note: This report flags issues for review. It does not silently change your source data.")
    return findings 
def refresh_quality_report():
    quality_text.configure(state="normal")
    quality_text.delete("1.0", "end")
    quality_text.insert("end", "\n".join(make_quality_report(df)))
    quality_text.configure(state="disabled")  
def build_monthly_revenue(data):
    date_col = get_date_column(data)
    revenue = get_revenue(data)
    if date_col is None or revenue is None:
        return None
    work = pd.DataFrame({
        "Date": pd.to_datetime(data[date_col], errors="coerce"),
        "Revenue": revenue
    }).dropna()
    if work.empty:
        return None
    work["Month"] = work["Date"].dt.to_period("M")
    return work.groupby("Month")["Revenue"].sum().sort_index()
def forecast_next_months(data, months_ahead=3):
    monthly = build_monthly_revenue(data)
    if monthly is None or len(monthly) < 3:
        return None, "Forecast needs a date column and at least 3 months of sales history."

    y = monthly.values.astype(float)
    x = np.arange(len(y), dtype=float)
    slope, intercept = np.polyfit(x, y, 1)
    future_x = np.arange(len(y), len(y) + months_ahead, dtype=float)
    predicted = slope * future_x + intercept
    predicted = np.maximum(predicted, 0)
    last_period = monthly.index[-1]
    future_periods = [last_period + i for i in range(1, months_ahead + 1)]
    forecast = pd.Series(predicted, index=future_periods, name="Forecast Revenue")
    return (monthly, forecast), None
def create_insight_lines(data):
    if data is None or data.empty:
        return ["Upload a dataset to generate insights."]
    revenue = get_revenue(data)
    if revenue is None:
        return ["Revenue insights need a Revenue/Sales column or Quantity and Price columns."]
    lines = ["BUSINESS INSIGHTS", "=" * 50]
    kpis = calculate_kpis(data)
    lines.append(f"Revenue in current filtered data: {money(kpis['revenue'])}")
    lines.append(f"Orders: {kpis['orders']:,}")
    lines.append(f"Average order value: {money(kpis['aov'])}")
    product_col = get_product_column(data)
    if product_col:
        by_product = pd.DataFrame({"product": data[product_col], "revenue": revenue}).dropna()
        by_product = by_product.groupby("product")["revenue"].sum().sort_values(ascending=False)
        if not by_product.empty:
            lines.append("")
            lines.append(f"Top product by revenue: {by_product.index[0]} ({money(by_product.iloc[0])})")
            if len(by_product) > 1:
                lines.append(f"Lowest product by revenue: {by_product.index[-1]} ({money(by_product.iloc[-1])})")
    region_col = get_region_column(data)
    if region_col:
        by_region = pd.DataFrame({"region": data[region_col], "revenue": revenue}).dropna()
        by_region = by_region.groupby("region")["revenue"].sum().sort_values(ascending=False)
        if not by_region.empty:
            lines.append("")
            lines.append(f"Top region by revenue: {by_region.index[0]} ({money(by_region.iloc[0])})")
            if len(by_region) > 1:
                lines.append(f"Lowest region by revenue: {by_region.index[-1]} ({money(by_region.iloc[-1])})")
    profit_col = find_column(data, "profit", "gross_profit", "profit_amount")
    if profit_col:
        profit = pd.to_numeric(data[profit_col], errors="coerce").sum()
        lines.append("")
        lines.append(f"Total profit: {money(profit)}")
        if kpis["revenue"]:
            lines.append(f"Profit margin: {profit / kpis['revenue'] * 100:.2f}%")
            if profit / kpis["revenue"] < 0.10:
                lines.append("Recommendation: Review product costs, discounts, and pricing because the observed profit margin is below 10%.")
            else:
                lines.append("Recommendation: Monitor whether this profit margin remains stable across products and regions.")
    monthly = build_monthly_revenue(data)
    if monthly is not None and not monthly.empty:
        lines.append("")
        lines.append(f"Highest-revenue month in available history: {monthly.idxmax()} ({money(monthly.max())})")
        if len(monthly) >= 2:
            previous = monthly.iloc[-2]
            current = monthly.iloc[-1]
            if previous != 0:
                change = (current - previous) / abs(previous) * 100
                arrow = "↗" if change >= 0 else "↘"
                lines.append(f"Latest month vs previous month: {arrow} {change:+.1f}%")
                if change < 0:
                    lines.append("Recommendation: Investigate whether the latest decline is seasonal, product-specific, or region-specific.")
    lines.append("")
    lines.append("INTERPRETATION NOTE")
    lines.append("These are descriptive patterns, not proof of cause. Check context before acting on recommendations.")
    return lines
def refresh_insights():
    global forecast_cache
    insights_text.configure(state="normal")
    insights_text.delete("1.0", "end")
    insights_text.insert("end", "\n".join(create_insight_lines(filtered_df)))
    insights_text.insert("end", "\n\nSALES FORECAST\n" + "=" * 50 + "\n")
    result, error = forecast_next_months(filtered_df, 3) if filtered_df is not None else (None, "Upload data first.")
    forecast_cache = result
    if error:
        insights_text.insert("end", error)
    else:
        historical, forecast = result
        insights_text.insert("end", "Simple linear-trend estimate for the next 3 months:\n")
        for period, value in forecast.items():
            insights_text.insert("end", f"  • {period}: {money(value)}\n")
        insights_text.insert("end", "\nLimitations: this baseline does not model seasonality, promotions, or external factors.")
    insights_text.configure(state="disabled")
    clear_frame(forecast_chart_holder)
    if forecast_cache:
        historical, forecast = forecast_cache
        fig = Figure(figsize=(8, 2.6), dpi=95, facecolor=BG)
        ax = fig.add_subplot(111)
        ax.set_facecolor(CARD)
        ax.plot([str(x) for x in historical.index], historical.values, marker="o",
                color=CYAN, linewidth=2, label="Actual")
        ax.plot([str(x) for x in forecast.index], forecast.values, marker="o",
                linestyle="--", color=ORANGE, linewidth=2, label="Forecast")
        ax.tick_params(colors=WHITE, labelsize=8)
        ax.set_title("Historical and Forecast Revenue", color=WHITE, fontweight="bold")
        ax.grid(axis="y", color=GRID, alpha=0.35)
        ax.legend(facecolor=CARD, labelcolor=WHITE)
        fig.tight_layout()
        embed_chart(forecast_chart_holder, fig)
def update_chart_dropdowns():
    if df is None:
        return
    cols = [str(c) for c in df.columns]
    x_combo.configure(values=cols or ["No columns"])
    x_combo.set(cols[0] if cols else "No columns")
    numeric = [str(c) for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
    y_options = ["None"] + numeric
    y_combo.configure(values=y_options)
    y_combo.set(numeric[0] if numeric else "None")
def generate_custom_chart():
    if filtered_df is None or filtered_df.empty:
        messagebox.showwarning("No data", "Upload a dataset and make sure the filters return rows.")
        return
    x_col = x_combo.get()
    y_col = y_combo.get()
    chart_type = chart_type_combo.get()
    title = chart_title_entry.get().strip() or "Custom Sales Chart"
    if x_col not in filtered_df.columns:
        messagebox.showwarning("Choose a column", "Please choose a valid X-axis column.")
        return
    if y_col == "None":
        y_col = None
    elif y_col not in filtered_df.columns:
        messagebox.showwarning("Choose a column", "Please choose a valid Y-axis column.")
        return
    clear_frame(custom_chart_holder)
    try:
        fig = create_chart(filtered_df, chart_type, x_col, y_col, title)
        embed_chart(custom_chart_holder, fig)
    except Exception as exc:
        messagebox.showerror("Chart error", str(exc))
def upload_file():
    global df, filtered_df, active_file_name
    file_path = filedialog.askopenfilename(
        title="Choose a sales dataset",
        filetypes=[
            ("Supported data files", "*.csv *.xlsx *.xls"),
            ("CSV files", "*.csv"),
            ("Excel files", "*.xlsx *.xls"),
        ]
    )
    if not file_path:
        return
    try:
        extension = Path(file_path).suffix.lower()
        new_data = pd.read_csv(file_path) if extension == ".csv" else pd.read_excel(file_path)

        if new_data.empty:
            messagebox.showwarning("Empty file", "The selected file contains no rows.")
            return
        new_data.columns = [str(col).strip() for col in new_data.columns]
        original_name = Path(file_path).name
        destination = UPLOAD_FOLDER / original_name
        version = 1
        while destination.exists():
            destination = UPLOAD_FOLDER / f"{Path(original_name).stem}_{version}{extension}"
            version += 1
        shutil.copy2(file_path, destination)
        df = new_data
        filtered_df = df.copy()
        active_file_name = destination.name
        configure_filter_values(df)
        update_chart_dropdowns()
        apply_filters()
        page_subtitle.configure(text=f"Active dataset: {active_file_name}  •  {len(df):,} rows")
        messagebox.showinfo(
            "Upload successful",
            f"Dataset loaded and saved.\n\nRows: {len(df):,}\nColumns: {len(df.columns)}\nSaved copy: {destination}"
        )
    except Exception as exc:
        messagebox.showerror("Upload error", f"Could not load this file.\n\nDetails: {exc}")
def export_filtered_csv():
    if filtered_df is None:
        messagebox.showwarning("No data", "Upload a dataset first.")
        return
    path = filedialog.asksaveasfilename(
        title="Save filtered data",
        defaultextension=".csv",
        filetypes=[("CSV files", "*.csv")]
    )
    if not path:
        return
    try:
        filtered_df.to_csv(path, index=False)
        messagebox.showinfo("Export complete", f"Saved filtered data to:\n{path}")
    except Exception as exc:
        messagebox.showerror("Export error", str(exc))
def refresh_pdf_page():
    pdf_info.configure(state="normal")
    pdf_info.delete("1.0", "end")
    if filtered_df is None:
        text = "Upload a dataset first. The report will use the current filters and search."
    else:
        kpis = calculate_kpis(filtered_df)
        text = (
            "PDF REPORT PREVIEW\n"
            "==================\n"
            f"Dataset: {active_file_name}\n"
            f"Rows in current view: {len(filtered_df):,}\n\n"
            "The generated PDF includes:\n"
            f"• Total revenue: {money(kpis['revenue'])}\n"
            f"• Total orders: {kpis['orders']:,}\n"
            f"• Units sold: {kpis['units']:,.0f}\n"
            f"• Average order value: {money(kpis['aov'])}\n"
            f"• Profit: {money(kpis['profit']) if kpis['profit'] is not None else 'Not available'}\n"
            "• Sales charts and data-quality findings\n"
            "• Business insights, recommendations, and forecast when supported by data\n"
        )
    pdf_info.insert("end", text)
    pdf_info.configure(state="disabled")
def generate_pdf_report():
    if filtered_df is None or filtered_df.empty:
        messagebox.showwarning("No data", "Upload a dataset and make sure filters return rows.")
        return
    path = filedialog.asksaveasfilename(
        title="Save Sales Analysis PDF",
        initialfile=f"Sales_Report_{datetime.now():%Y%m%d}.pdf",
        defaultextension=".pdf",
        filetypes=[("PDF files", "*.pdf")]
    )
    if not path:
        return
    temporary_images = []
    try:
        doc = SimpleDocTemplate(
            path, pagesize=landscape(A4),
            rightMargin=1.2 * cm, leftMargin=1.2 * cm,
            topMargin=1.2 * cm, bottomMargin=1.2 * cm
        )
        styles = getSampleStyleSheet()
        styles.add(ParagraphStyle(
            name="PurpleTitle", parent=styles["Title"],
            textColor=colors.HexColor("#6D28D9"), alignment=TA_CENTER,
            fontName="Helvetica-Bold", fontSize=22, leading=26, spaceAfter=12
        ))
        styles.add(ParagraphStyle(
            name="SectionPurple", parent=styles["Heading2"],
            textColor=colors.HexColor("#7E22CE"), spaceBefore=10, spaceAfter=7
        ))
        story = []
        kpis = calculate_kpis(filtered_df)
        story.append(Paragraph("Sales Data Analyzer Pro", styles["PurpleTitle"]))
        story.append(Paragraph("Sales Performance & Business Insights Report", styles["Heading2"]))
        story.append(Paragraph(f"Generated: {datetime.now():%d %B %Y, %H:%M}", styles["Normal"]))
        story.append(Paragraph(f"Dataset: {active_file_name}", styles["Normal"]))
        story.append(Paragraph(f"Current filtered records: {len(filtered_df):,}", styles["Normal"]))
        story.append(Spacer(1, 12))
        story.append(Paragraph("1. Executive KPI Summary", styles["SectionPurple"]))
        kpi_rows = [
            ["Metric", "Value"],
            ["Total Revenue", money(kpis["revenue"])],
            ["Total Orders", f'{kpis["orders"]:,}'],
            ["Units Sold", f'{kpis["units"]:,.0f}'],
            ["Average Order Value", money(kpis["aov"])],
            ["Total Profit", money(kpis["profit"]) if kpis["profit"] is not None else "Not available"],
            ["Profit Margin", f'{kpis["margin"]:.2f}%' if kpis["margin"] is not None else "Not available"],
        ]
        table = Table(kpi_rows, colWidths=[7 * cm, 7 * cm])
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4C1D95")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#F5F3FF")),
            ("TEXTCOLOR", (0, 1), (-1, -1), colors.HexColor("#241832")),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#C4B5FD")),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("PADDING", (0, 0), (-1, -1), 7),
        ]))
        story.append(table)
        story.append(Spacer(1, 14))
        revenue = get_revenue(filtered_df)
        product_col = get_product_column(filtered_df)
        region_col = get_region_column(filtered_df)
        date_col = get_date_column(filtered_df)
        quantity_col = find_column(filtered_df, "Quantity", "Qty", "Units Sold", "Unit Sold", "Units")
        category_col = find_column(filtered_df, "Category", "Product Category", "Segment", "Department")
        order_col = find_column(filtered_df, "Order ID", "Order_ID", "OrderID", "Invoice", "Invoice ID", "Transaction ID", "Order Number")
        dashboard_fig = Figure(figsize=(14.0, 8.0), dpi=160, facecolor="#100B1D")
        dashboard_fig.subplots_adjust(left=0.060, right=0.970, top=0.700, bottom=0.095,
                                      hspace=0.52, wspace=0.24)
        dashboard_fig.text(0.045, 0.955, "SALES & REVENUE DASHBOARD", color="#F8F5FF",
                           fontsize=21, fontweight="bold", ha="left", va="top")
        dashboard_fig.text(0.045, 0.905,
                           f"{active_file_name}  |  {len(filtered_df):,} filtered rows  |  Generated {datetime.now():%d %b %Y}",
                           color="#B9AFCB", fontsize=9, ha="left", va="top")
        kpi_display = [
            ("TOTAL REVENUE", money(kpis["revenue"]), "#FB923C"),
            ("TOTAL ORDERS", f'{kpis["orders"]:,}', "#67E8F9"),
            ("UNITS SOLD", f'{kpis["units"]:,.0f}', "#4ADE80"),
            ("AVERAGE ORDER VALUE", money(kpis["aov"]), "#F472B6"),
            ("TOTAL PROFIT", money(kpis["profit"]) if kpis["profit"] is not None else "N/A", "#A855F7"),
        ]
        for i, (label, value, accent) in enumerate(kpi_display):
            x = 0.045 + i * 0.19
            dashboard_fig.text(x, 0.852, label, color="#B9AFCB", fontsize=7.2,
                               fontweight="bold", ha="left", va="center",
                               bbox=dict(boxstyle="round,pad=0.55", facecolor="#2B1A42",
                                         edgecolor="#56366E", linewidth=0.8))
            dashboard_fig.text(x, 0.802, value, color=accent, fontsize=10.2,
                               fontweight="bold", ha="left", va="center")

        axes = [dashboard_fig.add_subplot(2, 2, i) for i in range(1, 5)]
        chart_bg = "#211532"
        grid_color = "#56366E"
        chart_colors = ["#FB923C", "#F472B6", "#A855F7", "#67E8F9", "#4ADE80", "#C084FC", "#FDBA74"]
        def style_pdf_axis(ax, title, ylabel=None):
            ax.set_facecolor(chart_bg)
            ax.set_title(title, color="#F8F5FF", fontsize=10, fontweight="bold", pad=8)
            ax.tick_params(colors="#F8F5FF", labelsize=7)
            ax.grid(axis="y", color=grid_color, alpha=0.45)
            for spine in ax.spines.values():
                spine.set_color(grid_color)
            if ylabel:
                ax.set_ylabel(ylabel, color="#B9AFCB", fontsize=7)
        # Chart 1: Revenue by product (or a useful category fallback).
        first_group = product_col or category_col or region_col
        if revenue is not None and first_group:
            temp = pd.DataFrame({"group": filtered_df[first_group].astype(str), "revenue": pd.to_numeric(revenue, errors="coerce")})
            grouped = temp.dropna().groupby("group")["revenue"].sum().sort_values(ascending=False).head(10)
            axes[0].bar(grouped.index, grouped.values, color=chart_colors[0])
            axes[0].tick_params(axis="x", rotation=22)
            style_pdf_axis(axes[0], f"Revenue by {first_group}", "Revenue (₹)")
        else:
            axes[0].text(0.5, 0.5, "Revenue/product fields unavailable", color="#F8F5FF", ha="center", va="center", transform=axes[0].transAxes)
            style_pdf_axis(axes[0], "Revenue by Product")
        # Chart 2: Regional revenue share (or category share fallback).
        second_group = region_col or category_col or product_col
        if revenue is not None and second_group:
            temp = pd.DataFrame({"group": filtered_df[second_group].astype(str), "revenue": pd.to_numeric(revenue, errors="coerce")})
            grouped = temp.dropna().groupby("group")["revenue"].sum().sort_values(ascending=False).head(7)
            grouped = grouped[grouped > 0]
            if not grouped.empty:
                wedges, _, _ = axes[1].pie(grouped.values, labels=grouped.index, autopct="%1.0f%%",
                    startangle=90, textprops={"color": "#F8F5FF", "fontsize": 7}, colors=chart_colors[:len(grouped)])
                axes[1].set_title(f"Revenue Share by {second_group}", color="#F8F5FF", fontsize=10, fontweight="bold", pad=8)
            else:
                axes[1].text(0.5, 0.5, "No positive revenue values", color="#F8F5FF", ha="center", va="center", transform=axes[1].transAxes)
                style_pdf_axis(axes[1], f"Revenue Share by {second_group}")
        else:
            axes[1].text(0.5, 0.5, "Region/category fields unavailable", color="#F8F5FF", ha="center", va="center", transform=axes[1].transAxes)
            style_pdf_axis(axes[1], "Revenue Share by Region")
        # Chart 3: Monthly revenue trend, using real dates when available.
        if date_col and revenue is not None:
            date_values = pd.to_datetime(filtered_df[date_col], errors="coerce")
            month_data = pd.DataFrame({"month": date_values.dt.to_period("M").astype(str),
                                       "revenue": pd.to_numeric(revenue, errors="coerce")}).dropna()
            monthly = month_data.groupby("month")["revenue"].sum().sort_index().tail(18)
            if not monthly.empty:
                axes[2].plot(monthly.index, monthly.values, color="#FB923C", marker="o", linewidth=2.2, markersize=3.5)
                axes[2].fill_between(range(len(monthly)), monthly.values, alpha=0.12, color="#F472B6")
                axes[2].set_xticks(range(len(monthly)))
                axes[2].set_xticklabels(monthly.index, rotation=35, ha="right")
                style_pdf_axis(axes[2], "Monthly Revenue Trend", "Revenue (₹)")
            else:
                axes[2].text(0.5, 0.5, "No valid dates for monthly trend", color="#F8F5FF", ha="center", va="center", transform=axes[2].transAxes)
                style_pdf_axis(axes[2], "Monthly Revenue Trend")
        else:
            axes[2].text(0.5, 0.5, "Date or revenue column unavailable", color="#F8F5FF", ha="center", va="center", transform=axes[2].transAxes)
            style_pdf_axis(axes[2], "Monthly Revenue Trend")
        # Chart 4: Units by product; fallback to order counts or category revenue.
        if product_col and quantity_col:
            temp = filtered_df[[product_col, quantity_col]].copy()
            temp[quantity_col] = pd.to_numeric(temp[quantity_col], errors="coerce")
            grouped = temp.dropna().groupby(product_col)[quantity_col].sum().sort_values(ascending=False).head(10)
            axes[3].bar(grouped.index.astype(str), grouped.values, color="#A855F7")
            axes[3].tick_params(axis="x", rotation=22)
            style_pdf_axis(axes[3], "Units Sold by Product", "Units")
        elif region_col and order_col:
            grouped = filtered_df.groupby(region_col)[order_col].nunique().sort_values(ascending=False).head(10)
            axes[3].bar(grouped.index.astype(str), grouped.values, color="#67E8F9")
            axes[3].tick_params(axis="x", rotation=22)
            style_pdf_axis(axes[3], "Orders by Region", "Unique orders")
        elif revenue is not None and category_col:
            temp = pd.DataFrame({"category": filtered_df[category_col].astype(str), "revenue": pd.to_numeric(revenue, errors="coerce")})
            grouped = temp.dropna().groupby("category")["revenue"].sum().sort_values(ascending=False).head(10)
            axes[3].bar(grouped.index, grouped.values, color="#67E8F9")
            axes[3].tick_params(axis="x", rotation=22)
            style_pdf_axis(axes[3], "Revenue by Category", "Revenue (₹)")
        else:
            axes[3].text(0.5, 0.5, "Quantity/order/category fields unavailable", color="#F8F5FF", ha="center", va="center", transform=axes[3].transAxes)
            style_pdf_axis(axes[3], "Sales Breakdown")
        dashboard_img = REPORT_FOLDER / "pdf_full_dashboard.png"
        dashboard_fig.savefig(dashboard_img, facecolor=dashboard_fig.get_facecolor(), dpi=160, bbox_inches="tight")
        temporary_images.append(dashboard_img)
        story.append(PageBreak())
        story.append(Paragraph("Full Dashboard Snapshot", styles["SectionPurple"]))
        # Fit the image inside the landscape page without stretching it.
        dashboard_pdf_image = PDFImage(str(dashboard_img), width=25.8 * cm, height=14.7 * cm)
        dashboard_pdf_image.hAlign = "CENTER"
        dashboard_pdf_image._restrictSize(25.8 * cm, 14.7 * cm)
        story.append(dashboard_pdf_image)
        story.append(PageBreak())
        if product_col and revenue is not None:
            temp = filtered_df.copy()
            temp["_Report_Revenue"] = revenue
            fig = create_chart(temp, "bar", product_col, "_Report_Revenue", "Revenue by Product")
            img_path = REPORT_FOLDER / "pdf_product_chart.png"
            fig.savefig(img_path, facecolor=fig.get_facecolor(), dpi=150)
            temporary_images.append(img_path)
            story.append(Paragraph("2. Revenue by Product", styles["SectionPurple"]))
            story.append(PDFImage(str(img_path), width=16 * cm, height=8.5 * cm))
            story.append(Spacer(1, 8))
        if region_col and revenue is not None:
            temp = filtered_df.copy()
            temp["_Report_Revenue"] = revenue
            fig = create_chart(temp, "pie", region_col, "_Report_Revenue", "Revenue by Region")
            img_path = REPORT_FOLDER / "pdf_region_chart.png"
            fig.savefig(img_path, facecolor=fig.get_facecolor(), dpi=150)
            temporary_images.append(img_path)
            story.append(Paragraph("3. Revenue by Region", styles["SectionPurple"]))
            story.append(PDFImage(str(img_path), width=15 * cm, height=8 * cm))
            story.append(Spacer(1, 8))
        story.append(PageBreak())
        story.append(Paragraph("4. Business Insights & Recommendations", styles["SectionPurple"]))
        for line in create_insight_lines(filtered_df):
            # Escape ampersands to prevent Paragraph from treating them as markup.
            safe_line = line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            story.append(Paragraph(safe_line or " ", styles["Normal"]))
            story.append(Spacer(1, 4))
        story.append(Spacer(1, 10))
        story.append(Paragraph("5. Data Quality Review", styles["SectionPurple"]))
        for line in make_quality_report(df):
            safe_line = line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            story.append(Paragraph(safe_line or " ", styles["Normal"]))
            story.append(Spacer(1, 3))
        story.append(Spacer(1, 10))
        story.append(Paragraph(
            "Forecasting note: the app uses a simple linear trend as a baseline and only when "
            "at least three monthly observations are available. Predictions are estimates, not guarantees.",
            styles["Italic"]
        ))
        doc.build(story)
        messagebox.showinfo("PDF created", f"Your report was saved to:\n{path}")
    except Exception as exc:
        messagebox.showerror("PDF report error", f"Could not create the PDF.\n\nDetails: {exc}")
ctk.CTkButton(
    sidebar, text="＋ Upload Dataset", command=upload_file,
    height=42, corner_radius=10, fg_color=PURPLE,
    hover_color="#7E22CE", font=(FONT, 12, "bold")
).pack(side="bottom", fill="x", padx=12, pady=(0, 10))    
def initialize_app():
    update_kpis(None)
    refresh_dashboard_charts()
    refresh_quality_report()
    refresh_insights()
    refresh_pdf_page()
    show_page("Dashboard")
initialize_app()
root.mainloop()
