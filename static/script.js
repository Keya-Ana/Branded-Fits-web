 
        tailwind.config = {
            theme: {
                extend: {
                    colors: {
                        brand: {
                            gold: '#C89D66',
                            goldLight: '#E5C99F',
                            dark: '#1A1A1A',
                            charcoal: '#262626',
                            cream: '#FAF8F4',
                            sand: '#F4EFE6',
                            grayMuted: '#777777',
                            border: '#E8E2D9'
                        }
                    },
                    fontFamily: {
                        sans: ['Inter', 'sans-serif'],
                        serif: ['Playfair Display', 'serif']
                    }
                }
            }
        }
// Example form submit handler
document.getElementById('checkoutForm')?.addEventListener('submit', function(e) {
  e.preventDefault();

  const orderData = {
    fullName: document.getElementById('checkoutName').value,
    email: document.getElementById('checkoutEmail').value,
    phone: document.getElementById('checkoutPhone').value,
    address: document.getElementById('checkoutAddress').value,
    region: document.getElementById('checkoutRegion').value,
    totalPrice: 180 // Total order cost in GHC
  };

  processMoMoPayment(orderData);
});