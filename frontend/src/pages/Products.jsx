import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";

const Products = () => {
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchProducts = async () => {
      try {
        setLoading(true);
        const response = await api.get("/products/");
        setProducts(response.data);
        setError(null);
      } catch (err) {
        console.error("Error fetching products:", err);
        setError("Failed to load products. Please check your connection.");
      } finally {
        setLoading(false);
      }
    };

    fetchProducts();
  }, []);

  if (loading) {
    return (
      <section className="py-5 bg-light" style={{ minHeight: "50vh" }}>
        <div className="container d-flex justify-content-center align-items-center h-100">
          <div className="spinner-border text-primary" role="status">
            <span className="visually-hidden">Loading...</span>
          </div>
        </div>
      </section>
    );
  }

  if (error) {
    return (
      <section className="py-5 bg-light">
        <div className="container text-center">
          <div className="alert alert-danger" role="alert">
            {error}
          </div>
          <button
            className="btn btn-primary"
            onClick={() => window.location.reload()}
          >
            Retry
          </button>
        </div>
      </section>
    );
  }

  return (
    <section id="products" className="py-5 bg-light">
      <div className="container">
        <div className="text-center mb-5">
          <h2 className="display-5 fw-bold mb-3">Clothing &amp; Style</h2>
          <p className="lead text-muted">
            Find your new everyday favorites, then select Buy Now to view details
            and add them to your cart.
          </p>
        </div>

        <div className="d-flex flex-wrap justify-content-start gap-4">
          {products?.length > 0 ? (
            products.map((product) => (
              <div
                key={product?.id}
                className="product-card bg-white shadow-sm mb-4"
                style={{ width: "18rem" }}
              >
                <div className="product-image-wrapper overflow-hidden">
                  <img
                    src={product?.image}
                    alt={product?.name}
                    className="product-image w-100"
                    style={{ height: "200px", objectFit: "cover" }}
                  />
                </div>

                <div className="p-3 d-flex flex-column flex-grow-1">
                  <h5
                    className="fw-bold mb-2 text-truncate"
                    title={product?.name}
                  >
                    {product?.name}
                  </h5>
                  <p className="text-muted flex-grow-1 mb-3">
                    {product?.description
                      ? `${product.description.substring(0, 80)}${product.description.length > 80 ? "..." : ""}`
                      : "No description available"}
                  </p>

                  <div className="d-flex justify-content-between align-items-center mb-3">
                    <span className="h5 text-primary fw-bold">
                      ${product?.price}
                    </span>
                    <small
                      className={`fw-semibold ${product?.stock > 0 ? "text-success" : "text-danger"}`}
                    >
                      {product?.stock > 0
                        ? `${product.stock} in stock`
                        : "Out of stock"}
                    </small>
                  </div>

                  <Link
                    to={`/product/${product?.id}`}
                    className={`btn btn-primary rounded-pill w-100 ${product?.stock === 0 ? "disabled" : ""}`}
                    aria-disabled={product?.stock === 0}
                    tabIndex={product?.stock === 0 ? -1 : undefined}
                  >
                    Buy Now
                  </Link>
                </div>
              </div>
            ))
          ) : (
            <div className="col-12 text-center">
              <p>No products found.</p>
            </div>
          )}
        </div>
      </div>
    </section>
  );
};

export default Products;
