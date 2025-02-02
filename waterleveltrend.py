import dash
from dash import dcc, html, Input, Output
import pandas as pd
import plotly.express as px
import pymannkendall as mk
import gdown
import os

# 📌 دانلود فایل CSV از Google Drive
FILE_ID = "1tjkeW3uyw6gUhOQSS8kp-Y2vel_QOsk4"  # جایگزین با FILE_ID داده‌های شما
GDRIVE_URL = f"https://drive.google.com/uc?id={FILE_ID}"
CSV_FILE = "combined_waterlevel.csv"

# اگر فایل قبلاً دانلود نشده باشد، آن را دریافت کن
if not os.path.exists(CSV_FILE):
    print("📥 در حال دانلود داده‌ها از Google Drive...")
    gdown.download(GDRIVE_URL, CSV_FILE, quiet=False)
    print("✅ فایل CSV با موفقیت دانلود شد!")

# 📌 خواندن داده‌ها از CSV (لود فقط ستون‌های موردنیاز برای بهینه‌سازی حافظه)
use_cols = ['ostan', 'UTM', 'gregorian_date', 'sath_ab_jadid', 'taraz', 'sath-ab']
df = pd.read_csv(CSV_FILE, encoding='utf-8-sig', low_memory=False, usecols=use_cols)

# 📌 اطمینان از اینکه 'gregorian_date' در فرمت صحیح است
df['gregorian_date'] = pd.to_datetime(df['gregorian_date'], errors='coerce')
df = df.dropna(subset=['gregorian_date'])

print("✅ داده‌ها آماده پردازش هستند!")
print("📌 نام ستون‌ها:", df.columns.tolist())

# 📌 مقداردهی اولیه به Dash
app = dash.Dash(__name__)

# 📌 رابط کاربری داشبورد
app.layout = html.Div([
    html.H1("تحلیل روند سطح آب", style={'textAlign': 'center'}),

    # انتخاب استان
    html.Div([
        html.Label("انتخاب استان:"),
        dcc.Dropdown(
            id='province-filter',
            options=[{'label': province, 'value': province} for province in sorted(df['ostan'].dropna().unique())],
            multi=True,
            placeholder="استان را انتخاب کنید"
        ),
    ], style={'width': '50%', 'padding': '10px'}),

    # انتخاب UTM
    html.Div([
        html.Label("انتخاب UTM:"),
        dcc.Dropdown(id='utm-filter', multi=True, placeholder="UTM را انتخاب کنید"),
    ], style={'width': '50%', 'padding': '10px'}),

    # نمایش محدوده
    html.Div([
        html.Label("محدوده انتخابی:"),
        html.Div(id='mahdoodeh-display', style={'padding': '10px', 'border': '1px solid #ccc', 'width': '50%'}),
    ]),

    # انتخاب متغیر سطح آب
    html.Div([
        html.Label("انتخاب متغیر سطح آب:"),
        dcc.Dropdown(
            id='variable-filter',
            options=[
                {'label': 'سطح آب جدید', 'value': 'sath_ab_jadid'},
                {'label': 'تراز', 'value': 'taraz'},
                {'label': 'سطح آب', 'value': 'sath-ab'}
            ],
            value='sath_ab_jadid',  # مقدار پیش‌فرض
            placeholder="متغیر مورد نظر را انتخاب کنید"
        ),
    ], style={'width': '50%', 'padding': '10px'}),

    # نمودار
    dcc.Graph(id='waterlevel-trend-plot'),

    # تحلیل آماری Mann-Kendall و شیب سن
    html.Div([
        html.Label("تحلیل آماری Mann-Kendall و Sen’s Slope:"),
        html.Div(id='trend-analysis-display', style={'padding': '10px', 'border': '1px solid #ccc', 'width': '80%'}),
    ]),

    # خلاصه سطح استان
    html.Div([
        html.Label("خلاصه تحلیل سطح استان:"),
        html.Div(id='province-summary-display', style={'padding': '10px', 'border': '1px solid #ccc', 'width': '80%'}),
    ]),
])

# 📌 بروز رسانی لیست UTM بر اساس استان انتخاب شده
@app.callback(
    Output('utm-filter', 'options'),
    Input('province-filter', 'value')
)
def update_utm_dropdown(selected_provinces):
    if not selected_provinces:
        return []
    filtered_df = df[df['ostan'].isin(selected_provinces)]
    return [{'label': utm, 'value': utm} for utm in filtered_df['UTM'].dropna().unique()]

# 📌 نمایش محدوده برای UTM انتخاب شده
@app.callback(
    Output('mahdoodeh-display', 'children'),
    Input('utm-filter', 'value')
)
def update_mahdoodeh_display(selected_utms):
    if not selected_utms:
        return "هیچ UTM انتخاب نشده است"
    mahdoodeh_list = df.loc[df['UTM'].isin(selected_utms), 'ostan'].dropna().unique()
    return ', '.join(mahdoodeh_list) if len(mahdoodeh_list) > 0 else "محدوده‌ای یافت نشد"

# 📌 نمایش نمودار روند سطح آب
@app.callback(
    [Output('waterlevel-trend-plot', 'figure'),
     Output('trend-analysis-display', 'children'),
     Output('province-summary-display', 'children')],
    [Input('province-filter', 'value'),
     Input('utm-filter', 'value'),
     Input('variable-filter', 'value')]
)
def update_plot_and_analysis(selected_provinces, selected_utms, selected_variable):
    if not selected_provinces:
        return px.line(title="هیچ استانی انتخاب نشده است"), "هیچ استانی انتخاب نشده است", "هیچ استانی انتخاب نشده است"

    filtered_df = df[df['ostan'].isin(selected_provinces)]

    if selected_utms:
        filtered_df = filtered_df[filtered_df['UTM'].isin(selected_utms)]

    if filtered_df.empty:
        return px.line(title="داده‌ای موجود نیست"), "داده‌ای موجود نیست", "داده‌ای موجود نیست"

    # 📌 رسم نمودار
    fig = px.line(
        filtered_df,
        x='gregorian_date',
        y=selected_variable,
        color='UTM',
        title=f"روند {selected_variable} بر اساس استان و UTM",
        labels={'gregorian_date': 'تاریخ میلادی', selected_variable: selected_variable},
        template='plotly_dark'
    )
    fig.update_traces(mode='lines+markers')

    # 📌 تحلیل آماری سطح استان
    utm_groups = filtered_df.groupby('UTM')
    significant_count = 0
    nonsignificant_count = 0
    total_utm = len(utm_groups)

    for utm, group in utm_groups:
        values = group[selected_variable].dropna().values
        if len(values) < 5:
            continue
        mk_result = mk.original_test(values)
        if mk_result.p < 0.05:
            significant_count += 1
        else:
            nonsignificant_count += 1

    ratio = significant_count / nonsignificant_count if nonsignificant_count > 0 else float("inf")

    province_summary = (f"مجموع UTMها: {total_utm}, "
                        f"دارای روند معنی‌دار: {significant_count}, "
                        f"بدون روند: {nonsignificant_count}, "
                        f"نسبت (رونددار:بدون روند): {ratio:.2f}")

    return fig, html.Div([f"UTM: {utm}, روند: {'صعودی' if mk.original_test(filtered_df[filtered_df['UTM'] == utm][selected_variable].dropna().values).z > 0 else 'نزولی'}" for utm in selected_utms]), province_summary

# 📌 اجرای برنامه در Railway یا Google Colab
if __name__ == '__main__':
    app.run_server(debug=True, host='0.0.0.0', port=8080)
