from django.apps import AppConfig
import logging
import signal
import atexit
import os

logger = logging.getLogger(__name__)


class FastaProcessorConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'fasta_processor'
    
    def ready(self):
        """
        Initialize databases at server startup (runs ONCE, not per job).
        This is the critical performance fix - moves heavy operations from job-time to boot-time.
        Also registers signal handlers for graceful shutdown.
        """
        # Only run in main process (not in migrations, tests, etc.)
        import sys
        if 'migrate' in sys.argv or 'makemigrations' in sys.argv or 'test' in sys.argv:
            return
        
        # Register signal handlers for graceful shutdown
        self._register_shutdown_handlers()
        
        try:
            from .services import EggnogProcessor
            
            # Get paths from settings or use defaults
            from django.conf import settings
            eggnog_db_path = getattr(settings, 'EGGNOG_DB_PATH', '/home/ser1dai/eggnog_db_final')
            kofam_db_path = getattr(settings, 'KOFAM_DB_PATH', '/home/ser1dai/eggnog_db_final/kofam_db')
            
            # LAZY INITIALIZATION: Initialize databases in background (non-blocking)
            # This allows server to start immediately, databases will be ready when first job runs
            logger.info("🚀 Starting database initialization in background (non-blocking)...")
            import threading
            def init_in_background():
                try:
                    result = EggnogProcessor.initialize_databases(eggnog_db_path, kofam_db_path)
                    if result:
                        logger.info("✅ Background database initialization complete - pipeline is ready!")
                    else:
                        logger.warning("⚠️  Background initialization failed - will retry on first job")
                except Exception as e:
                    logger.error(f"❌ Background initialization error: {e}")
            
            # Start initialization in background thread (non-blocking)
            init_thread = threading.Thread(target=init_in_background, daemon=True)
            init_thread.start()
            logger.info("✅ Server started - database initialization running in background")
                
        except Exception as e:
            logger.error(f"❌ Error during server startup initialization: {str(e)}")
            logger.exception("Startup initialization error")
            # Don't crash server - allow lazy initialization
    
    def _register_shutdown_handlers(self):
        """Register signal handlers to cleanup processes on server shutdown"""
        def signal_handler(signum, frame):
            logger.info(f"🛑 Received signal {signum} - cleaning up processes...")
            from .services import _cleanup_all_processes
            _cleanup_all_processes()
            # Re-raise signal to allow normal shutdown
            signal.signal(signum, signal.SIG_DFL)
            os.kill(os.getpid(), signum)
        
        # Register handlers for common termination signals
        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)
        
        # Also register atexit (backup)
        from .services import _cleanup_all_processes
        atexit.register(_cleanup_all_processes)
