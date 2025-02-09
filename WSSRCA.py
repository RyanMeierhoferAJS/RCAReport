import streamlit as st
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
import pandas as pd
import matplotlib.pyplot as plt
import os

# File Path for Report
output_pdf = "Wet_Sugar_Screw_RCA_Report.pdf"

def generate_trend_plot():
    plt.figure(figsize=(6, 3))
    x = ["Jan", "Feb", "Mar", "Apr", "May"]
    y = [3.2, 4.1, 5.6, 7.2, 8.1]  # Example Vibration Trend
    plt.plot(x, y, marker='o', linestyle='-', color='b', label='Vibration Trend (mm/s)')
    plt.xlabel("Month")
    plt.ylabel("Vibration Velocity RMS (mm/s)")
    plt.title("Wet Sugar Screw Vibration Trend")
    plt.legend()
    plt.grid()
    plt.savefig("trend_plot.png")
    plt.close()

def generate_pdf_report(data):
    doc = SimpleDocTemplate(output_pdf, pagesize=A4)
    elements = []
    styles = getSampleStyleSheet()
    
    elements.append(Paragraph("Root Cause Analysis Report", styles['Title']))
    elements.append(Spacer(1, 20))
    elements.append(Paragraph("Wet Sugar Screw Conveyor", styles['Heading2']))
    elements.append(Spacer(1, 40))
    
    elements.append(Paragraph("Executive Summary", styles['Heading2']))
    elements.append(Paragraph("This report outlines the Root Cause Analysis (RCA) for the Wet Sugar Screw failure, investigating vibration anomalies and operational challenges.", styles['Normal']))
    elements.append(Spacer(1, 20))
    
    table_data = [["Failure Mode", "Root Cause", "Corrective Action"]] + data.values.tolist()
    table = Table(table_data)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    elements.append(table)
    elements.append(Spacer(1, 20))
    
    generate_trend_plot()
    if os.path.exists("trend_plot.png"):
        elements.append(Paragraph("Vibration Analysis", styles['Heading2']))
        elements.append(Spacer(1, 10))
        elements.append(Image("trend_plot.png", width=400, height=200))
        elements.append(Spacer(1, 20))
    
    elements.append(Paragraph("Recommendations", styles['Heading2']))
    elements.append(Paragraph("To mitigate recurrence, it is recommended to implement load monitoring, standardize alignment procedures, and enforce lubrication schedules.", styles['Normal']))
    elements.append(Spacer(1, 20))
    
    doc.build(elements)
    st.success(f"PDF report '{output_pdf}' generated successfully!")

st.title("Wet Sugar Screw RCA Report Generator")

st.write("Fill in the details below to generate the RCA Report.")

failure_modes = []
root_causes = []
corrective_actions = []

num_entries = st.number_input("Number of Failure Modes", min_value=1, max_value=10, value=3)
for i in range(num_entries):
    col1, col2, col3 = st.columns(3)
    failure_modes.append(col1.text_input(f"Failure Mode {i+1}", ""))
    root_causes.append(col2.text_input(f"Root Cause {i+1}", ""))
    corrective_actions.append(col3.text_input(f"Corrective Action {i+1}", ""))

if st.button("Generate PDF Report"):
    df = pd.DataFrame({
        "Failure Mode": failure_modes,
        "Root Cause": root_causes,
        "Corrective Action": corrective_actions
    })
    generate_pdf_report(df)
