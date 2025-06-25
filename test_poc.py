#!/usr/bin/env python3
"""
Test script to verify POC functionality
"""

import os
import sys
import asyncio
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from src.posabit_adapter import POSaBITAdapter
from src.search_service import SearchService
from src.strain_classifier import StrainClassifier
from src.database import get_db_connection
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_database_connection():
    """Test database connectivity"""
    print("\n🔍 Testing database connection...")
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            result = cur.fetchone()
        conn.close()
        print("✅ Database connection successful")
        return True
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False

async def test_posabit_connection():
    """Test POSaBIT API connection"""
    print("\n🔍 Testing POSaBIT connection...")
    try:
        adapter = POSaBITAdapter()
        data = adapter.fetch_raw_feed()
        menu_items = data.get('product_data', {}).get('menu_items', [])
        print(f"✅ POSaBIT connection successful - found {len(menu_items)} products")
        
        if menu_items:
            sample = adapter.normalize_product(menu_items[0])
            print(f"📋 Sample product: {sample['name']} - {sample['thc_pct']}% THC - ${sample['price']}")
        
        return True
    except Exception as e:
        print(f"❌ POSaBIT connection failed: {e}")
        return False

async def test_search_service():
    """Test search functionality"""
    print("\n🔍 Testing search service...")
    try:
        service = SearchService()
        
        # Sample products for testing
        sample_products = [
            {
                'sku': 'BD001',
                'name': 'Blue Dream 3.5g',
                'brand': 'Premium Cannabis',
                'form_factor': 'flower',
                'strain': 'Blue Dream',
                'thc_pct': 22.5,
                'cbd_pct': 0.1,
                'price': 35.00,
                'category': 'Flower'
            },
            {
                'sku': 'GG002',
                'name': 'Gorilla Glue #4 Vape Cart',
                'brand': 'Vape Co',
                'form_factor': 'vape',
                'strain': 'Gorilla Glue #4',
                'thc_pct': 85.0,
                'cbd_pct': 0.5,
                'price': 45.00,
                'category': 'Vape'
            }
        ]
        
        # Test search
        results = await service.search("something for relaxation", sample_products)
        print(f"✅ Search service working - returned {len(results)} results")
        
        if results:
            print(f"📋 Sample result: {results[0]['name']} - {results[0]['reason']}")
        
        return True
    except Exception as e:
        print(f"❌ Search service failed: {e}")
        return False

async def test_strain_classifier():
    """Test strain classification"""
    print("\n🔍 Testing strain classifier...")
    try:
        classifier = StrainClassifier()
        
        # Test classification
        result = classifier.classify_strain("Blue Dream")
        print(f"✅ Strain classifier working")
        print(f"📋 Blue Dream classification: {result['strain_type']} - {', '.join(result['effects'][:3])}")
        
        return True
    except Exception as e:
        print(f"❌ Strain classifier failed: {e}")
        return False

async def test_full_integration():
    """Test full integration with real data"""
    print("\n🔍 Testing full integration...")
    try:
        # Fetch real products
        adapter = POSaBITAdapter()
        products = await adapter.fetch_products("pend-oreille-cannabis-co")
        
        if not products:
            print("⚠️  No products found - run ingest.py first")
            return False
        
        # Test search with real products
        service = SearchService()
        results = await service.search("something for sleep", products[:50])  # Limit for testing
        
        print(f"✅ Full integration test successful")
        print(f"📊 Searched {len(products)} products, found {len(results)} matches")
        
        if results:
            for i, result in enumerate(results[:2], 1):
                print(f"   {i}. {result['name']} - {result['reason']}")
        
        return True
    except Exception as e:
        print(f"❌ Full integration test failed: {e}")
        return False

async def main():
    """Run all tests"""
    print("🧪 WeedFinder.ai POC Test Suite")
    print("=" * 50)
    
    tests = [
        ("Database Connection", test_database_connection),
        ("POSaBIT API", test_posabit_connection),
        ("Search Service", test_search_service),
        ("Strain Classifier", test_strain_classifier),
        ("Full Integration", test_full_integration),
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        try:
            results[test_name] = await test_func()
        except Exception as e:
            print(f"❌ {test_name} test crashed: {e}")
            results[test_name] = False
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 Test Results Summary:")
    print("=" * 50)
    
    passed = 0
    total = len(tests)
    
    for test_name, passed_test in results.items():
        status = "✅ PASS" if passed_test else "❌ FAIL"
        print(f"{test_name:20} {status}")
        if passed_test:
            passed += 1
    
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed! Your POC is ready to use.")
        print("\nNext steps:")
        print("1. Start the API: python app.py")
        print("2. Open widget/index.html in your browser")
        print("3. Try searching: 'something for relaxation'")
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Check the error messages above.")
        print("\nCommon issues:")
        print("- Database not running or configured incorrectly")
        print("- Missing environment variables in .env file")
        print("- OpenAI API key not set or invalid")
        print("- POSaBIT credentials incorrect")
    
    return passed == total

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)