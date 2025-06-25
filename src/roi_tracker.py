import pandas as pd
import logging
from typing import Dict, Optional
from datetime import datetime, timedelta
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from .database import get_db_cursor, get_store_by_slug

logger = logging.getLogger(__name__)

class ROITracker:
    """Track and calculate ROI metrics for stores"""
    
    def __init__(self):
        self.smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_user = os.getenv("SMTP_USER")
        self.smtp_password = os.getenv("SMTP_PASSWORD")
    
    async def import_baseline(self, store_slug: str, csv_data: Dict) -> float:
        """Import baseline sales data from CSV"""
        try:
            store = get_store_by_slug(store_slug)
            if not store:
                raise ValueError(f"Store not found: {store_slug}")
            
            store_id = store['id']
            
            # If csv_data contains file path, read it
            if 'file_path' in csv_data:
                df = pd.read_csv(csv_data['file_path'])
            elif 'data' in csv_data:
                # Direct data provided
                df = pd.DataFrame(csv_data['data'])
            else:
                raise ValueError("No valid CSV data provided")
            
            # Ensure required columns exist
            required_cols = ['closed_at', 'subtotal']
            missing_cols = [col for col in required_cols if col not in df.columns]
            if missing_cols:
                raise ValueError(f"Missing required columns: {missing_cols}")
            
            # Convert closed_at to datetime
            df['closed_at'] = pd.to_datetime(df['closed_at'])
            
            # Filter to last 30 days for baseline (14 days before widget activation)
            cutoff_date = datetime.now() - timedelta(days=14)
            baseline_df = df[df['closed_at'] < cutoff_date]
            
            # Store baseline data
            with get_db_cursor() as cur:
                # Clear existing baseline for this store
                cur.execute("DELETE FROM sales_baseline WHERE store_id = %s", (store_id,))
                
                # Insert baseline records
                for _, row in baseline_df.iterrows():
                    cur.execute("""
                        INSERT INTO sales_baseline (store_id, ticket_id, subtotal, closed_at)
                        VALUES (%s, %s, %s, %s)
                    """, (
                        store_id,
                        row.get('ticket_id', f"baseline_{row.name}"),
                        float(row['subtotal']),
                        row['closed_at']
                    ))
                
                # Calculate baseline AOV
                baseline_aov = baseline_df['subtotal'].mean()
                
                logger.info(f"Imported {len(baseline_df)} baseline records for {store_slug}, AOV: ${baseline_aov:.2f}")
                return baseline_aov
                
        except Exception as e:
            logger.error(f"Error importing baseline for {store_slug}: {e}")
            raise
    
    async def calculate_metrics(self, store_slug: str) -> Dict:
        """Calculate current ROI metrics for a store"""
        try:
            store = get_store_by_slug(store_slug)
            if not store:
                raise ValueError(f"Store not found: {store_slug}")
            
            store_id = store['id']
            
            with get_db_cursor() as cur:
                # Get baseline AOV
                cur.execute("""
                    SELECT AVG(subtotal) as baseline_aov, COUNT(*) as baseline_count
                    FROM sales_baseline 
                    WHERE store_id = %s
                """, (store_id,))
                
                baseline_result = cur.fetchone()
                baseline_aov = float(baseline_result['baseline_aov'] or 0)
                baseline_count = baseline_result['baseline_count']
                
                if baseline_count == 0:
                    raise ValueError("No baseline data found. Please import baseline sales first.")
                
                # Get current 7-day AOV
                cur.execute("""
                    SELECT AVG(subtotal) as current_aov, COUNT(*) as current_count
                    FROM sales_current 
                    WHERE store_id = %s 
                    AND closed_at >= NOW() - INTERVAL '7 days'
                """, (store_id,))
                
                current_result = cur.fetchone()
                current_aov = float(current_result['current_aov'] or baseline_aov)
                current_count = current_result['current_count']
                
                # Calculate lift metrics
                lift_abs = current_aov - baseline_aov
                lift_pct = (lift_abs / baseline_aov * 100) if baseline_aov > 0 else 0
                
                # Estimate weekly impact (assuming 150 tickets/day average)
                daily_tickets = max(current_count / 7, 150) if current_count > 0 else 150
                weekly_impact = lift_abs * daily_tickets * 7
                
                metrics = {
                    'baseline_aov': round(baseline_aov, 2),
                    'current_aov': round(current_aov, 2),
                    'lift_abs': round(lift_abs, 2),
                    'lift_pct': round(lift_pct, 1),
                    'weekly_impact': round(weekly_impact, 2),
                    'baseline_count': baseline_count,
                    'current_count': current_count
                }
                
                # Store metrics in database
                cur.execute("""
                    INSERT INTO store_metrics (store_id, date, baseline_aov, current_aov, lift_abs, lift_pct)
                    VALUES (%s, CURRENT_DATE, %s, %s, %s, %s)
                    ON CONFLICT (store_id, date) 
                    DO UPDATE SET
                        baseline_aov = EXCLUDED.baseline_aov,
                        current_aov = EXCLUDED.current_aov,
                        lift_abs = EXCLUDED.lift_abs,
                        lift_pct = EXCLUDED.lift_pct
                """, (store_id, baseline_aov, current_aov, lift_abs, lift_pct))
                
                logger.info(f"Calculated metrics for {store_slug}: {lift_pct:.1f}% lift, ${weekly_impact:.2f} weekly impact")
                return metrics
                
        except Exception as e:
            logger.error(f"Error calculating metrics for {store_slug}: {e}")
            raise
    
    def generate_weekly_report_html(self, store_name: str, metrics: Dict) -> str:
        """Generate HTML email report"""
        return f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; text-align: center;">
                <h1 style="margin: 0;">🌿 WeedFinder Impact Report</h1>
                <p style="margin: 5px 0 0 0;">Week ending {datetime.now().strftime('%B %d, %Y')}</p>
            </div>
            
            <div style="padding: 20px; background: #f8f9fa;">
                <h2 style="color: #333; margin-top: 0;">📊 {store_name} Performance</h2>
                
                <div style="background: white; padding: 15px; border-radius: 8px; margin: 15px 0; border-left: 4px solid #28a745;">
                    <h3 style="color: #28a745; margin: 0 0 10px 0;">💰 Average Basket Size</h3>
                    <p style="margin: 5px 0; font-size: 16px;">
                        <strong>Before Widget:</strong> ${metrics['baseline_aov']:.2f}<br>
                        <strong>After Widget:</strong> ${metrics['current_aov']:.2f} 
                        <span style="color: {'#28a745' if metrics['lift_pct'] > 0 else '#dc3545'}; font-weight: bold;">
                            ({'+' if metrics['lift_pct'] > 0 else ''}{metrics['lift_pct']:.1f}%)
                        </span>
                    </p>
                </div>
                
                <div style="background: white; padding: 15px; border-radius: 8px; margin: 15px 0; border-left: 4px solid #007bff;">
                    <h3 style="color: #007bff; margin: 0 0 10px 0;">📈 Weekly Revenue Impact</h3>
                    <p style="font-size: 24px; font-weight: bold; color: {'#28a745' if metrics['weekly_impact'] > 0 else '#dc3545'}; margin: 10px 0;">
                        ${'+' if metrics['weekly_impact'] > 0 else ''}{metrics['weekly_impact']:.2f}
                    </p>
                    <p style="font-size: 14px; color: #666; margin: 5px 0;">
                        Based on basket lift × estimated daily transactions
                    </p>
                </div>
                
                <div style="background: white; padding: 15px; border-radius: 8px; margin: 15px 0; border-left: 4px solid #6f42c1;">
                    <h3 style="color: #6f42c1; margin: 0 0 10px 0;">🔍 Search Activity</h3>
                    <p style="margin: 5px 0;">
                        Widget searches are helping customers find exactly what they need, 
                        leading to higher-value purchases and better customer satisfaction.
                    </p>
                </div>
                
                <div style="background: #e9ecef; padding: 15px; border-radius: 8px; margin: 20px 0;">
                    <h4 style="margin: 0 0 10px 0; color: #495057;">📋 Methodology</h4>
                    <p style="font-size: 14px; color: #6c757d; margin: 0; line-height: 1.4;">
                        Compares 14-day baseline period to current 7-day rolling average using your POS export data. 
                        Revenue impact calculated based on basket lift × estimated daily transaction volume.
                    </p>
                </div>
                
                <div style="text-align: center; margin: 20px 0;">
                    <p style="color: #666;">Questions about your results?</p>
                    <a href="mailto:support@weedfinder.ai" style="background: #007bff; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">
                        Contact Support
                    </a>
                </div>
            </div>
            
            <div style="background: #343a40; color: #adb5bd; padding: 15px; text-align: center; font-size: 12px;">
                <p style="margin: 0;">WeedFinder.ai - AI-Powered Cannabis Product Discovery</p>
                <p style="margin: 5px 0 0 0;">This report was generated automatically from your POS data.</p>
            </div>
        </body>
        </html>
        """
    
    async def send_weekly_report(self, store_slug: str, recipient_email: str) -> bool:
        """Send weekly ROI report via email"""
        try:
            store = get_store_by_slug(store_slug)
            if not store:
                raise ValueError(f"Store not found: {store_slug}")
            
            # Calculate current metrics
            metrics = await self.calculate_metrics(store_slug)
            
            # Generate email content
            subject = f"WeedFinder Weekly Impact: ${'+' if metrics['weekly_impact'] > 0 else ''}{metrics['weekly_impact']:.0f}"
            html_body = self.generate_weekly_report_html(store['name'], metrics)
            
            # Create email message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = f"WeedFinder Reports <{self.smtp_user}>"
            msg['To'] = recipient_email
            
            # Add HTML content
            html_part = MIMEText(html_body, 'html')
            msg.attach(html_part)
            
            # Send email
            if self.smtp_user and self.smtp_password:
                with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                    server.starttls()
                    server.login(self.smtp_user, self.smtp_password)
                    server.send_message(msg)
                
                logger.info(f"Weekly report sent to {recipient_email} for {store_slug}")
                return True
            else:
                logger.warning("SMTP credentials not configured, email not sent")
                # In development, just log the email content
                logger.info(f"Would send email to {recipient_email}:\n{subject}\n{html_body}")
                return False
                
        except Exception as e:
            logger.error(f"Error sending weekly report for {store_slug}: {e}")
            return False
    
    async def import_current_sales(self, store_slug: str, csv_data: Dict) -> int:
        """Import current sales data for ROI calculation"""
        try:
            store = get_store_by_slug(store_slug)
            if not store:
                raise ValueError(f"Store not found: {store_slug}")
            
            store_id = store['id']
            
            # Process CSV data
            if 'file_path' in csv_data:
                df = pd.read_csv(csv_data['file_path'])
            elif 'data' in csv_data:
                df = pd.DataFrame(csv_data['data'])
            else:
                raise ValueError("No valid CSV data provided")
            
            # Convert closed_at to datetime
            df['closed_at'] = pd.to_datetime(df['closed_at'])
            
            # Store current sales data
            with get_db_cursor() as cur:
                count = 0
                for _, row in df.iterrows():
                    cur.execute("""
                        INSERT INTO sales_current (store_id, ticket_id, subtotal, item_notes, closed_at)
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT DO NOTHING
                    """, (
                        store_id,
                        row.get('ticket_id', f"current_{row.name}"),
                        float(row['subtotal']),
                        row.get('item_notes', ''),
                        row['closed_at']
                    ))
                    count += 1
                
                logger.info(f"Imported {count} current sales records for {store_slug}")
                return count
                
        except Exception as e:
            logger.error(f"Error importing current sales for {store_slug}: {e}")
            raise

def test_roi_tracker():
    """Test the ROI tracker"""
    import asyncio
    
    async def run_test():
        tracker = ROITracker()
        
        # Test with sample data
        sample_baseline = {
            'data': [
                {'ticket_id': 'T001', 'subtotal': 35.50, 'closed_at': '2024-01-01 10:00:00'},
                {'ticket_id': 'T002', 'subtotal': 42.25, 'closed_at': '2024-01-01 11:00:00'},
                {'ticket_id': 'T003', 'subtotal': 28.75, 'closed_at': '2024-01-01 12:00:00'},
            ]
        }
        
        try:
            baseline_aov = await tracker.import_baseline('test-store', sample_baseline)
            print(f"Baseline AOV: ${baseline_aov:.2f}")
            
            metrics = await tracker.calculate_metrics('test-store')
            print(f"Metrics: {metrics}")
            
        except Exception as e:
            print(f"Test failed: {e}")
    
    asyncio.run(run_test())

if __name__ == "__main__":
    test_roi_tracker()