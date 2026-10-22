 
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

  try {
    const file = document.getElementById('productImageInput').files[0];
    if (!file) {
      throw new Error('Choose a product image first.');
    }

    const formData = new FormData();
    formData.append('file', file);
    formData.append('upload_preset', 'branded');

    const cloudResponse = await fetch('https://api.cloudinary.com/v1_1/upzfj7fw/image/upload', {
      method: 'POST',
      body: formData
    });
    const cloudData = await cloudResponse.json();
    if (!cloudResponse.ok || !cloudData.secure_url) {
      throw new Error(cloudData.error?.message || 'The product image could not be uploaded.');
    }

    const productPayload = {
      name: document.getElementById('productName').value.trim(),
      price: document.getElementById('productPrice').value,
      category: document.getElementById('productCategory').value,
      image: cloudData.secure_url
    };
    const response = await fetch('/api/products', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(productPayload)
    });
    const result = await response.json();
    if (!response.ok) {
      throw new Error(result.error || 'The product could not be saved.');
    }

    products.push({
      id: String(result.id),
      title: productPayload.name,
      price: Number(productPayload.price),
      category: productPayload.category,
      image: productPayload.image,
      desc: ''
    });
    saveState();
    renderFeaturedGrid();
    renderShopGrid();
    renderAdminTables();
    updateAdminStats();
    event.target.reset();
    showToast('Product uploaded successfully!');
  } catch (error) {
    console.error('Unable to add product:', error);
    showToast(error.message || 'Unable to add product. Please try again.');
  }
}
