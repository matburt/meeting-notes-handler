#!/usr/bin/env python3
"""Meeting Notes Handler CLI - Main entry point."""

import sys
import logging
from pathlib import Path
from datetime import datetime
import click

from . import __version__
from .config import Config
from .google_meet_fetcher import GoogleMeetFetcher
from .file_organizer import FileOrganizer

def setup_logging(level: str = "INFO"):
    """Setup logging configuration."""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
        ]
    )

@click.group(invoke_without_command=True)
@click.option('--config', '-c', help='Configuration file path')
@click.option('--log-level', default='INFO', help='Logging level')
@click.option('--version', is_flag=True, help='Show version and exit')
@click.pass_context
def cli(ctx, config, log_level, version):
    """Meeting Notes Handler - Fetch and organize Google Meet notes."""
    if version:
        click.echo(f"Meeting Notes Handler v{__version__}")
        return
    
    # If no command is provided, show help
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())
        return
    
    ctx.ensure_object(dict)
    
    setup_logging(log_level)
    
    try:
        ctx.obj['config'] = Config(config)
        logger = logging.getLogger(__name__)
        logger.info("Meeting Notes Handler initialized")
    except Exception as e:
        click.echo(f"Error initializing configuration: {e}", err=True)
        sys.exit(1)

@cli.command()
@click.option('--days', '-d', default=None, type=int, help='Number of days back to fetch')
@click.option('--dry-run', is_flag=True, help='Preview without saving files')
@click.option('--week', '-w', help='Specific week to fetch (YYYY-WW format)')
@click.option('--accepted', is_flag=True, default=False, help='Only fetch notes from meetings you accepted or are tentative for.')
@click.option('--force', '-f', is_flag=True, default=False, help='Force re-fetch meetings even if already processed')
@click.option('--gemini-only', '-g', is_flag=True, default=False, help='Only fetch Gemini notes and transcripts, skip other documents')
@click.option('--smart-filter', '-s', is_flag=True, default=False, help='Apply smart content filtering to extract only new content from recurring meetings')
@click.pass_context
def fetch(ctx, days, dry_run, week, accepted, force, gemini_only, smart_filter):
    """Fetch meeting notes from Google Calendar and Docs."""
    config = ctx.obj['config']
    logger = logging.getLogger(__name__)
    
    if week:
        click.echo(f"Week-specific fetching not yet implemented: {week}")
        return
    
    click.echo("🔍 Fetching meeting notes...")
    if dry_run:
        click.echo("📋 DRY RUN - No files will be saved")
    if accepted:
        click.echo("✅ Filtering for accepted meetings only")
    if force:
        click.echo("🔄 FORCE MODE - Will re-fetch already processed meetings")
    if gemini_only:
        click.echo("🤖 GEMINI MODE - Only fetching Gemini notes and transcripts")
    if smart_filter:
        click.echo("🧠 SMART FILTER - Extracting only new content from recurring meetings")

    try:
        fetcher = GoogleMeetFetcher(config)
        
        click.echo("🔐 Authenticating with Google APIs...")
        if not fetcher.authenticate():
            click.echo("❌ Authentication failed", err=True)
            sys.exit(1)
        
        click.echo("✅ Authentication successful")
        
        # Fetch and process meetings
        results = fetcher.fetch_and_process_all(days_back=days, dry_run=dry_run, accepted_only=accepted, force_refetch=force, gemini_only=gemini_only, smart_filtering=smart_filter)
        
        if results['success']:
            click.echo(f"\n📊 Results:")
            click.echo(f"   Meetings found: {results['meetings_found']}")
            click.echo(f"   Meetings processed: {results['meetings_processed']}")
            if results.get('meetings_skipped', 0) > 0:
                click.echo(f"   Meetings skipped (already processed): {results['meetings_skipped']}")
            click.echo(f"   Meetings with notes: {results['meetings_with_notes']}")
            click.echo(f"   Total documents: {results['total_documents']}")
            
            if not dry_run:
                click.echo(f"   📁 Notes saved to: {config.output_directory}")
            
            # Show details of processed meetings
            if results['processed_meetings']:
                click.echo(f"\n📝 Processed meetings:")
                for meeting in results['processed_meetings']:
                    if meeting.get('skipped'):
                        status = "⏭️ "
                        date_str = datetime.fromisoformat(meeting['date']).strftime('%Y-%m-%d %H:%M')
                        click.echo(f"   {status} {date_str} - {meeting['title']} (skipped: {meeting.get('reason', 'already processed')})")
                    else:
                        status = "✅" if meeting['success'] else "❌"
                        date_str = datetime.fromisoformat(meeting['date']).strftime('%Y-%m-%d %H:%M')
                        click.echo(f"   {status} {date_str} - {meeting['title']} ({meeting['notes_count']} docs)")
            
            # Show errors if any
            if results['errors']:
                click.echo(f"\n⚠️  Errors encountered:")
                for error in results['errors']:
                    click.echo(f"   • {error}")
        else:
            click.echo(f"❌ Failed: {results.get('error', 'Unknown error')}", err=True)
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"Error during fetch operation: {e}")
        click.echo(f"❌ Error: {e}", err=True)
        sys.exit(1)

@cli.command()
@click.pass_context
def list_weeks(ctx):
    """List all available weeks with meeting notes."""
    config = ctx.obj['config']
    
    organizer = FileOrganizer(config.output_directory)
    weeks = organizer.list_weeks()
    
    if not weeks:
        click.echo("📂 No meeting notes found")
        return
    
    click.echo(f"📅 Available weeks ({len(weeks)} total):")
    for week in weeks:
        meetings = organizer.list_meetings_in_week(week)
        click.echo(f"   {week}: {len(meetings)} meetings")

@cli.command()
@click.argument('week')
@click.pass_context
def list_meetings(ctx, week):
    """List meetings in a specific week."""
    config = ctx.obj['config']
    
    organizer = FileOrganizer(config.output_directory)
    meetings = organizer.list_meetings_in_week(week)
    
    if not meetings:
        click.echo(f"📂 No meetings found for week {week}")
        return
    
    click.echo(f"📝 Meetings in week {week} ({len(meetings)} total):")
    for meeting_file in meetings:
        file_size = meeting_file.stat().st_size
        modified = datetime.fromtimestamp(meeting_file.stat().st_mtime)
        click.echo(f"   📄 {meeting_file.name} ({file_size} bytes, modified {modified.strftime('%Y-%m-%d %H:%M')})")

@cli.command()
@click.pass_context
def setup(ctx):
    """Setup Google API credentials and configuration."""
    config = ctx.obj['config']
    
    click.echo("🔧 Setting up Meeting Notes Handler")
    click.echo("\nChoose your preferred authentication method:")
    click.echo("\n1. 🚀 Google CLI (Recommended - Easiest)")
    click.echo("2. 📁 Manual credentials file")
    
    choice = click.prompt("Select option", type=click.Choice(['1', '2']), default='1')
    
    if choice == '1':
        click.echo("\n🚀 Setting up with Google CLI...")
        click.echo("\nIf you don't have gcloud CLI installed:")
        click.echo("   curl https://sdk.cloud.google.com | bash")
        click.echo("   exec -l $SHELL")
        click.echo("\nRun these commands:")
        click.echo("   gcloud auth application-default login --scopes=https://www.googleapis.com/auth/cloud-platform,https://www.googleapis.com/auth/calendar.readonly,https://www.googleapis.com/auth/drive.readonly,https://www.googleapis.com/auth/documents.readonly")
        click.echo("   gcloud services enable calendar-json.googleapis.com")
        click.echo("   gcloud services enable drive.googleapis.com") 
        click.echo("   gcloud services enable docs.googleapis.com")
        
        if click.confirm("\nHave you completed the gcloud setup?"):
            # Test authentication
            click.echo("\n🔐 Testing authentication...")
            try:
                fetcher = GoogleMeetFetcher(config)
                if fetcher.authenticate():
                    click.echo("✅ Authentication successful!")
                    click.echo("\n🎉 Setup complete! You can now use 'fetch' to get meeting notes.")
                else:
                    click.echo("❌ Authentication failed", err=True)
                    click.echo("Please ensure you've run the gcloud commands above.")
            except Exception as e:
                click.echo(f"❌ Error during authentication test: {e}", err=True)
    
    else:
        click.echo("\n📁 Manual credentials setup...")
        click.echo("This requires Google Cloud Console setup:")
        click.echo("\n1. Go to: https://console.cloud.google.com/")
        click.echo("2. Create a project and enable APIs (Calendar, Drive, Docs)")
        click.echo("3. Create OAuth 2.0 credentials for desktop application")
        click.echo("4. Download the credentials JSON file")
        
        creds_path = click.prompt(f"\nPath to credentials JSON file", 
                                 default=str(config.google_credentials_file))
        
        creds_file = Path(creds_path)
        if not creds_file.exists():
            click.echo(f"❌ Credentials file not found: {creds_file}", err=True)
            return
        
        # Copy credentials to project directory if not already there
        if creds_file != config.google_credentials_file:
            import shutil
            shutil.copy2(creds_file, config.google_credentials_file)
            click.echo(f"📋 Copied credentials to: {config.google_credentials_file}")
        
        # Test authentication
        click.echo("\n🔐 Testing authentication...")
        try:
            fetcher = GoogleMeetFetcher(config)
            if fetcher.authenticate():
                click.echo("✅ Authentication successful!")
                click.echo("\n🎉 Setup complete! You can now use 'fetch' to get meeting notes.")
            else:
                click.echo("❌ Authentication failed", err=True)
        except Exception as e:
            click.echo(f"❌ Error during authentication test: {e}", err=True)

@cli.command()
@click.pass_context
def config_show(ctx):
    """Show current configuration."""
    config = ctx.obj['config']
    
    click.echo("⚙️  Current Configuration:")
    click.echo(f"   📁 Output directory: {config.output_directory}")
    click.echo(f"   🔑 Credentials file: {config.google_credentials_file}")
    click.echo(f"   🎫 Token file: {config.google_token_file}")
    click.echo(f"   📅 Default days back: {config.days_back}")
    click.echo(f"   🔍 Calendar keywords: {', '.join(config.calendar_keywords)}")
    
    # Check file existence
    click.echo(f"\n📋 File Status:")
    click.echo(f"   Credentials: {'✅' if config.google_credentials_file.exists() else '❌'}")
    click.echo(f"   Token: {'✅' if config.google_token_file.exists() else '❌'}")
    click.echo(f"   Output dir: {'✅' if config.output_directory.exists() else '❌'}")

if __name__ == '__main__':
    cli()