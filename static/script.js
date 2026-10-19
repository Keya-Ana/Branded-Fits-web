 
        tailwind.config = {
            theme: {
                extend: {
                    colors: {
                        brand: {
                            gold: '#C89D66',
                            goldLight: '#E5C99F',
                            dark: '#1A1A1A',
                            charcoal: '#262626',
                            cream: '#FDFBF7',
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
async function handleAddProduct(event) {
  event.preventDefault();

  const fileInput = document.getElementById('productImageInput');
  const file = fileInput.files[0];

  // 1. Upload photo to Cloudinary
  const formData = new FormData();
  formData.append('file', file);
  formData.append('upload_preset', 'branded');

  const cloudResponse = await fetch('https://api.cloudinary.com/v1_1/upzfj7fw/image/upload', {
    method: 'POST',
    body: formData
  });
  const cloudData = await cloudResponse.json();
  const imageUrl = cloudData.secure_url; // Direct URL to the hosted image

  // 2. Save product details + image URL to Flask Backend
  const productPayload = {
    name: document.getElementById('productName').value,
    price: document.getElementById('productPrice').value,
    category: document.getElementById('productCategory').value,
    image: imageUrl
  };

  await fetch('http://127.0.0.1:5000', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(productPayload)
  });

  alert('Product uploaded successfully!');
  loadProducts(); // Refresh catalog view
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