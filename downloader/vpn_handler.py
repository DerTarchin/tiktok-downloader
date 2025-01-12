"""NordVPN handler functionality."""

import subprocess
import time
import random
from threading import Lock

class VPNHandler:
    def __init__(self, countries=None):
        """
        Initialize VPN handler.
        
        Args:
            countries: List of country codes to cycle through. If None, will use a default list
                      of countries known to work well with TikTok.
        """
        self.vpn_lock = Lock()
        self.current_country = None
        
        # Default to countries known to work well with TikTok if none specified
        self.countries = countries or [
            'us', 'ca', 'uk', 'de', 'fr', 'nl', 'se', 'no', 'jp', 'au'
        ]
        
    def connect(self, country=None):
        """Connect to VPN in specified country or a random one from the list."""
        with self.vpn_lock:
            try:
                # Disconnect first if already connected
                subprocess.run(['nordvpn', 'disconnect'], 
                             stdout=subprocess.PIPE, 
                             stderr=subprocess.PIPE)
                
                # Wait for disconnect
                time.sleep(2)
                
                # Select country
                target_country = country or random.choice(self.countries)
                
                # Connect to new server
                result = subprocess.run(['nordvpn', 'connect', target_country],
                                     stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE,
                                     text=True)
                
                if result.returncode == 0:
                    self.current_country = target_country
                    return True
                return False
                
            except Exception as e:
                print(f"VPN connection error: {str(e)}")
                return False
    
    def disconnect(self):
        """Disconnect from VPN."""
        with self.vpn_lock:
            try:
                subprocess.run(['nordvpn', 'disconnect'], 
                             stdout=subprocess.PIPE, 
                             stderr=subprocess.PIPE)
                self.current_country = None
                return True
            except Exception as e:
                print(f"VPN disconnection error: {str(e)}")
                return False
    
    def rotate(self):
        """Rotate to a new VPN server."""
        # Choose a different country than current
        available_countries = [c for c in self.countries if c != self.current_country]
        if not available_countries:
            available_countries = self.countries
            
        new_country = random.choice(available_countries)
        return self.connect(new_country)
        
    def get_status(self):
        """Get current VPN status."""
        try:
            result = subprocess.run(['nordvpn', 'status'],
                                 stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE,
                                 text=True)
            return result.stdout
        except Exception as e:
            return f"Error getting VPN status: {str(e)}" 