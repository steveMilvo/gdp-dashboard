/// Domain models. Aligned to Firestore collections per spec §6.1.
/// Ported from the Phase 1 MVP scaffold.

enum UserRole { merchant, customer, rider, farmer, admin }

enum OrderStatus {
  pending,
  confirmed,
  preparing,
  ready,
  riderAssigned,
  pickedUp,
  delivered,
  cancelled,
  disputed,
}

enum FoodHandlingCategory {
  rawFish,
  rawMeat,
  cookedFood,
  vegetables,
  eggs,
  dryGoods,
  beverages,
}

class Market {
  const Market({
    required this.id,
    required this.name,
    required this.city,
    required this.barangay,
    required this.lat,
    required this.lng,
  });

  final String id;
  final String name;
  final String city;
  final String barangay;
  final double lat;
  final double lng;
}

class Product {
  const Product({
    required this.id,
    required this.stallId,
    required this.name,
    required this.category,
    required this.pricePerUnit,
    required this.unit,
    required this.quantityAvailable,
    required this.foodHandlingCategory,
    this.aiDetectedName,
    this.aiConfidenceScore,
    this.photoUrl,
  });

  final String id;
  final String stallId;
  final String name;
  final String category;
  final String? aiDetectedName;
  final double? aiConfidenceScore;
  final double pricePerUnit;
  final String unit;
  final double quantityAvailable;
  final FoodHandlingCategory foodHandlingCategory;
  final String? photoUrl;
}

class OrderItem {
  const OrderItem({
    required this.productId,
    required this.name,
    required this.quantity,
    required this.unitPrice,
  });

  final String productId;
  final String name;
  final double quantity;
  final double unitPrice;

  double get subtotal => quantity * unitPrice;
}

class Order {
  const Order({
    required this.id,
    required this.customerId,
    required this.stallId,
    required this.status,
    required this.items,
    required this.deliveryFee,
    required this.deliveryLat,
    required this.deliveryLng,
    required this.landmarkNote,
    this.riderId,
    this.gcashReference,
  });

  final String id;
  final String customerId;
  final String stallId;
  final String? riderId;
  final OrderStatus status;
  final List<OrderItem> items;
  final double deliveryFee;
  final double deliveryLat;
  final double deliveryLng;
  final String landmarkNote;
  final String? gcashReference;

  double get subtotal =>
      items.fold(0, (sum, item) => sum + item.subtotal);

  double get total => subtotal + deliveryFee;

  Order copyWith({
    OrderStatus? status,
    String? riderId,
    String? gcashReference,
  }) =>
      Order(
        id: id,
        customerId: customerId,
        stallId: stallId,
        riderId: riderId ?? this.riderId,
        status: status ?? this.status,
        items: items,
        deliveryFee: deliveryFee,
        deliveryLat: deliveryLat,
        deliveryLng: deliveryLng,
        landmarkNote: landmarkNote,
        gcashReference: gcashReference ?? this.gcashReference,
      );
}
