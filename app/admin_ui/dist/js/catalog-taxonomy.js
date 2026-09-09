// A generic, broad category/subcategory taxonomy covering most product
// types a small-to-mid business might sell — physical goods, digital
// products, and services alike — so "Category" + "Sub-category" selects can
// meaningfully classify almost anything without needing free text. Not
// exhaustive (no taxonomy ever is); a business with a genuinely unusual
// product can still pick the closest fit or "Other".
export const CATALOG_TAXONOMY = {
  'Fashion & Apparel': [
    "Men's Clothing", "Women's Clothing", "Kids' Clothing", 'Unisex Clothing',
    'Shoes', 'Bags & Luggage', 'Jewelry & Watches', 'Sunglasses & Eyewear',
    'Belts, Hats & Scarves', 'Traditional & Native Wear', 'Lingerie & Underwear',
    'Other',
  ],
  'Beauty & Personal Care': [
    'Skincare', 'Makeup', 'Hair Care', 'Hair Extensions & Wigs', 'Fragrances & Perfumes',
    'Bath & Body', 'Nail Care', 'Men\'s Grooming', 'Beauty Tools & Accessories',
    'Other',
  ],
  'Electronics & Gadgets': [
    'Phones & Tablets', 'Phone Accessories', 'Computers & Laptops', 'Computer Accessories',
    'Audio & Headphones', 'TVs & Home Theatre', 'Cameras & Drones', 'Wearables & Smartwatches',
    'Chargers, Cables & Power Banks', 'Gaming Consoles & Accessories', 'Smart Home Devices',
    'Other',
  ],
  'Home & Living': [
    'Living Room Furniture', 'Bedroom Furniture', 'Kitchen & Dining Furniture', 'Office Furniture',
    'Kitchenware & Cookware', 'Bedding & Bath Linen', 'Home Décor & Wall Art', 'Rugs & Curtains',
    'Storage & Organization', 'Home Appliances', 'Lighting', 'Cleaning Supplies',
    'Other',
  ],
  'Food & Beverages': [
    'Groceries & Pantry', 'Fresh Produce', 'Meat, Poultry & Seafood', 'Snacks & Confectionery',
    'Baked Goods & Pastries', 'Soft Drinks & Juices', 'Alcoholic Beverages', 'Coffee & Tea',
    'Meal Prep & Catering', 'Spices, Herbs & Condiments', 'Baby Food',
    'Other',
  ],
  'Health & Wellness': [
    'Vitamins & Supplements', 'Fitness Equipment', 'Medical & First Aid Supplies',
    'Personal Hygiene', 'Mobility & Home Care Aids', 'Sexual Wellness', 'Weight Management',
    'Other',
  ],
  'Baby & Kids': [
    'Baby Clothing', 'Baby Gear (Strollers, Car Seats)', 'Diapers & Wipes', 'Feeding & Nursing',
    'Toys & Games', 'School Supplies & Backpacks', 'Kids\' Furniture', 'Maternity Wear',
    'Other',
  ],
  'Books, Media & Education': [
    'Fiction Books', 'Non-Fiction Books', 'Textbooks & Academic', 'Children\'s Books',
    'Ebooks & Audiobooks', 'Music & Vinyl', 'Movies & TV', 'Stationery & Office Supplies',
    'Other',
  ],
  'Digital Products': [
    'Software & Apps', 'Mobile Apps', 'Ebooks & Guides', 'Design Templates & Assets',
    'Stock Photos, Video & Audio', 'Online Courses', 'Software Licenses & Subscriptions',
    'NFTs & Digital Collectibles', 'Website & Domain Services',
    'Other',
  ],
  'Arts, Crafts & Hobbies': [
    'Handmade Goods', 'Art Supplies & Materials', 'Craft Materials', 'Sewing & Fabric',
    'Collectibles & Memorabilia', 'Musical Instruments', 'Model Kits & Puzzles',
    'Other',
  ],
  'Automotive': [
    'Car Parts & Components', 'Car Accessories & Electronics', 'Motorcycle & Bike Parts',
    'Car Care & Detailing', 'Tires & Wheels', 'Tools & Equipment',
    'Other',
  ],
  'Sports & Outdoors': [
    'Exercise & Fitness Equipment', 'Team Sports Gear', 'Outdoor & Camping Gear',
    'Cycling', 'Swimming & Water Sports', 'Sportswear & Footwear', 'Fan Gear & Merchandise',
    'Other',
  ],
  'Pet Supplies': [
    'Pet Food', 'Pet Grooming', 'Pet Toys & Accessories', 'Pet Health & Wellness',
    'Pet Housing & Carriers',
    'Other',
  ],
  'Office & Industrial': [
    'Office Supplies & Stationery', 'Office Furniture & Equipment', 'Packaging & Shipping Supplies',
    'Industrial Tools & Equipment', 'Safety & Workwear',
    'Other',
  ],
  'Services': [
    'Consulting & Business Services', 'Repairs & Maintenance', 'Event Planning & Rentals',
    'Beauty & Grooming Services', 'Delivery & Logistics', 'Cleaning Services',
    'Photography & Videography', 'Tutoring & Coaching', 'Legal & Financial Services',
    'IT & Tech Support', 'Professional Services',
    'Other',
  ],
  'Other': ['Other'],
};

export const CATALOG_CATEGORIES = Object.keys(CATALOG_TAXONOMY);

export function subcategoriesFor(category) {
  return CATALOG_TAXONOMY[category] || ['Other'];
}
