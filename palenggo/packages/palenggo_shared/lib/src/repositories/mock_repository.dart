import '../models/models.dart';

/// In-memory store for the Phase 1 demo. Uses static lists so a Riverpod
/// `Provider` can hand the same instance to merchant/customer/rider screens
/// inside a single app process.
///
/// Cross-app state sharing (merchant posts a product → customer sees it in a
/// different app) requires either:
///   1. Phase 1 step 7: swap this for a `FirestoreRepository`, or
///   2. Wire each app to the local Express backend over HTTP.
class MockPalengGoRepository {
  static final List<Product> _products = [
    const Product(
      id: 'prod_bangus_001',
      stallId: 'stall_47',
      name: 'Bangus',
      category: 'fish',
      aiDetectedName: 'Milkfish / Bangus',
      aiConfidenceScore: 0.91,
      pricePerUnit: 190,
      unit: 'kg',
      quantityAvailable: 20,
      foodHandlingCategory: FoodHandlingCategory.rawFish,
    ),
  ];

  static final List<Order> _orders = [];

  List<Product> listProducts() => List.unmodifiable(_products);

  Product postProduct(Product product) {
    _products.add(product);
    return product;
  }

  Order createOrder(Order order) {
    _orders.add(order);
    return order;
  }

  List<Order> openOrders() => _orders
      .where((o) =>
          o.status == OrderStatus.pending ||
          o.status == OrderStatus.confirmed)
      .toList();

  void updateOrderStatus(String orderId, OrderStatus status) {
    final i = _orders.indexWhere((o) => o.id == orderId);
    if (i == -1) return;
    _orders[i] = _orders[i].copyWith(status: status);
  }
}
